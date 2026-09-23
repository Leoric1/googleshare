"""GCS tools for retrieving policy documents.

Authentication relies on Application Default Credentials (ADC). When the agent
runs on Vertex AI Agent Engine with Agent Identity enabled, ADC automatically
resolves to the per-agent principal — no service-account key is involved.

IAM grant example (run once, replacing placeholders):

  gcloud storage buckets add-iam-policy-binding gs://POLICY_BUCKET \
    --member="principal://agents.global.org-ORG_ID.system.id.goog/resources/aiplatform/projects/PROJECT_NUMBER/locations/LOCATION/reasoningEngines/AGENT_ENGINE_ID" \
    --role="roles/storage.objectViewer"

All tools return a dict. On failure they return a structured error instead of
raising, so the LLM can surface a clean, user-facing message rather than a
Python traceback. Error shape:

  {
    "error": "<machine_code>",        # e.g. "permission_denied"
    "message": "<human-readable>",    # safe to show the user
    "remediation": "<what to do>",    # actionable next step
    "bucket": "...", "prefix": "...", # context echoed back
  }
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from google.api_core import exceptions as gax_exceptions
from google.auth import default
from google.auth import exceptions as gauth_exceptions
from google.cloud import storage

from . import config


@lru_cache(maxsize=1)
def _client() -> storage.Client:
    credentials, project = default()
    return storage.Client(
        project=config.PROJECT_ID or project,
        credentials=credentials,
    )


def _resolve_bucket(bucket: str | None) -> str:
    resolved = bucket or config.POLICY_BUCKET
    if not resolved:
        raise ValueError(
            "No bucket supplied and POLICY_BUCKET env var is not set."
        )
    return resolved


def _permission_denied(target: str, action: str) -> dict[str, Any]:
    return {
        "error": "permission_denied",
        "message": (
            f"I don't have permission to {action} at {target}. "
            "The agent's identity hasn't been granted access to this "
            "Cloud Storage location."
        ),
        "remediation": (
            "Ask a Google Cloud admin to grant this agent "
            "`roles/storage.objectViewer` on the bucket. The agent's principal "
            "is of the form "
            "`principal://agents.global.org-<ORG_ID>.system.id.goog/resources/"
            "aiplatform/projects/<PROJECT_NUMBER>/locations/<LOCATION>/"
            "reasoningEngines/<AGENT_ENGINE_ID>` — it can be retrieved from "
            "the reasoning engine's `spec.effectiveIdentity` field."
        ),
        "target": target,
    }


def _not_found(target: str) -> dict[str, Any]:
    return {
        "error": "not_found",
        "message": (
            f"Nothing found at {target}. The bucket may not exist, the object "
            "name may be wrong, or `POLICY_BUCKET` / `POLICY_PREFIX` may be "
            "misconfigured."
        ),
        "remediation": (
            "Verify the bucket exists and the agent's POLICY_BUCKET / "
            "POLICY_PREFIX environment variables point at the right location."
        ),
        "target": target,
    }


def _unauthenticated(target: str) -> dict[str, Any]:
    return {
        "error": "unauthenticated",
        "message": (
            f"The agent could not obtain credentials to access {target}. "
            "Application Default Credentials did not resolve."
        ),
        "remediation": (
            "If running on Vertex AI Agent Engine, verify the reasoning "
            "engine was deployed with `identity_type=AGENT_IDENTITY`. "
            "Locally, run `gcloud auth application-default login`."
        ),
        "target": target,
    }


def _unexpected(target: str, exc: BaseException) -> dict[str, Any]:
    return {
        "error": "unexpected",
        "message": (
            f"An unexpected error occurred while accessing {target}: "
            f"{type(exc).__name__}: {exc}"
        ),
        "remediation": (
            "Retry the request. If the error persists, check the reasoning "
            "engine logs in Cloud Logging."
        ),
        "target": target,
    }


def list_policies(bucket: str | None = None, prefix: str | None = None) -> dict:
    """List policy documents in the configured Cloud Storage bucket.

    Args:
      bucket: Override the default bucket. Optional.
      prefix: Override the default prefix filter. Optional.

    Returns:
      On success: {`bucket`, `prefix`, `documents`: [{name, size, updated, content_type}, ...]}.
      On failure: a structured `error` dict (permission_denied / not_found /
      unauthenticated / unexpected) with a human-readable `message` and
      `remediation` field — safe to surface to the user.
    """
    try:
        target_bucket = _resolve_bucket(bucket)
    except ValueError as e:
        return {
            "error": "misconfigured",
            "message": str(e),
            "remediation": "Set the POLICY_BUCKET env var on the deployed agent.",
        }
    target_prefix = prefix if prefix is not None else config.POLICY_PREFIX
    target = f"gs://{target_bucket}/{target_prefix}"

    try:
        blobs = _client().list_blobs(target_bucket, prefix=target_prefix)
        documents = [
            {
                "name": b.name,
                "size": b.size,
                "updated": b.updated.isoformat() if b.updated else None,
                "content_type": b.content_type,
            }
            for b in blobs
            if not b.name.endswith("/")
        ]
    except gax_exceptions.Forbidden:
        return _permission_denied(target, "list objects")
    except gax_exceptions.NotFound:
        return _not_found(target)
    except gauth_exceptions.DefaultCredentialsError:
        return _unauthenticated(target)
    except Exception as e:  # noqa: BLE001
        return _unexpected(target, e)

    return {"bucket": target_bucket, "prefix": target_prefix, "documents": documents}


def get_policy_document(name: str, bucket: str | None = None) -> dict:
    """Fetch a single policy document by object name and return its text.

    Args:
      name: Object name inside the bucket (e.g. `policies/acceptable-use.md`).
      bucket: Override the default bucket. Optional.

    Returns:
      On success: {`name`, `bucket`, `content_type`, `size`, `content`}.
      On binary / oversized docs: `content: null` with a `note`.
      On failure: a structured `error` dict (permission_denied / not_found /
      unauthenticated / unexpected) — safe to surface to the user.
    """
    try:
        target_bucket = _resolve_bucket(bucket)
    except ValueError as e:
        return {
            "error": "misconfigured",
            "message": str(e),
            "remediation": "Set the POLICY_BUCKET env var on the deployed agent.",
        }
    target = f"gs://{target_bucket}/{name}"

    try:
        blob = _client().bucket(target_bucket).get_blob(name)
    except gax_exceptions.Forbidden:
        return _permission_denied(target, "read this object")
    except gax_exceptions.NotFound:
        return _not_found(target)
    except gauth_exceptions.DefaultCredentialsError:
        return _unauthenticated(target)
    except Exception as e:  # noqa: BLE001
        return _unexpected(target, e)

    if blob is None:
        return _not_found(target)

    if blob.size and blob.size > config.MAX_DOC_BYTES:
        return {
            "name": blob.name,
            "bucket": target_bucket,
            "content_type": blob.content_type,
            "size": blob.size,
            "content": None,
            "note": f"Document exceeds MAX_DOC_BYTES ({config.MAX_DOC_BYTES}); returning metadata only.",
        }

    try:
        data = blob.download_as_bytes()
    except gax_exceptions.Forbidden:
        return _permission_denied(target, "download this object")
    except gax_exceptions.NotFound:
        return _not_found(target)
    except Exception as e:  # noqa: BLE001
        return _unexpected(target, e)

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return {
            "name": blob.name,
            "bucket": target_bucket,
            "content_type": blob.content_type,
            "size": blob.size,
            "content": None,
            "note": "Document is not UTF-8 text; ask user for a text-format policy or a different tool.",
        }

    return {
        "name": blob.name,
        "bucket": target_bucket,
        "content_type": blob.content_type,
        "size": blob.size,
        "content": text,
    }


def search_policies(query: str, bucket: str | None = None, prefix: str | None = None) -> dict:
    """Case-insensitive substring search across text policy documents.

    Loads each candidate object, decodes UTF-8, and returns matching snippets.
    Intended for small policy corpora; for large sets, back this with Vertex AI
    Search instead.

    Returns:
      On success: {`query`, `matches`: [{name, snippet}, ...]}.
      On failure (e.g. missing GCS access): propagates the structured `error`
      dict from `list_policies` so the LLM can surface a clean message.
    """
    listing = list_policies(bucket=bucket, prefix=prefix)
    if listing.get("error"):
        return {"query": query, **listing}

    q = query.lower().strip()
    if not q:
        return {"query": query, "matches": []}

    matches: list[dict] = []
    for doc in listing["documents"]:
        fetched = get_policy_document(doc["name"], bucket=listing["bucket"])
        if fetched.get("error"):
            # Skip individual-doc failures; surface access issues only if
            # _every_ doc failed (the list_policies path would have caught
            # bucket-wide denials already).
            continue
        content = fetched.get("content")
        if not content:
            continue
        lower = content.lower()
        idx = lower.find(q)
        if idx == -1:
            continue
        start = max(0, idx - 120)
        end = min(len(content), idx + len(q) + 120)
        matches.append(
            {
                "name": fetched["name"],
                "snippet": content[start:end],
            }
        )
    return {"query": query, "matches": matches}
