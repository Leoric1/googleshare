"""Deploy the policy + weather agent to Vertex AI Agent Engine with Agent Identity.

Usage:
  export GOOGLE_CLOUD_PROJECT=my-project
  export GOOGLE_CLOUD_LOCATION=us-central1
  export STAGING_BUCKET=my-agent-staging
  export POLICY_BUCKET=my-policy-docs
  python deploy.py

Prints the reasoning engine resource name — use it when registering the
agent with Gemini Enterprise (see register_gemini_enterprise.py).
"""

from __future__ import annotations

import os
import sys

import vertexai
from vertexai import types
from vertexai.agent_engines import AdkApp

from policy_agent.agent import root_agent


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing required env var: {name}")
    return value


def main() -> None:
    project = _require("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    staging_bucket = _require("STAGING_BUCKET")
    policy_bucket = _require("POLICY_BUCKET")
    policy_prefix = os.environ.get("POLICY_PREFIX", "policies/")
    display_name = os.environ.get("DISPLAY_NAME", "policy-weather-agent")

    # Auth Provider resource name (created by gcloud agent-identity auth-providers create)
    auth_provider_name = os.environ.get("AUTH_PROVIDER_NAME", "")
    # OpenWeatherMap API Key (fallback for query-param auth, since Auth Manager
    # injects as HTTP header but OpenWeatherMap expects ?appid= query param)
    openweather_api_key = os.environ.get("OPENWEATHER_API_KEY", "")

    client = vertexai.Client(
        project=project,
        location=location,
        http_options=dict(api_version="v1beta1"),
    )

    app = AdkApp(agent=root_agent)

    config_dict = {
        "display_name": display_name,
        "identity_type": types.IdentityType.AGENT_IDENTITY,
        "requirements": [
            "google-cloud-aiplatform[adk,agent_engines]",
            "google-cloud-storage>=2.18.0",
            "google-cloud-secret-manager>=2.20.0",
            "pydantic>=2.7.0",
            "cloudpickle>=3.0.0",
            "httpx>=0.27.0",
        ],
        "staging_bucket": f"gs://{staging_bucket}",
        "extra_packages": ["policy_agent"],
        # GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION are reserved by
        # Agent Engine and injected automatically — do not set them here.
        "env_vars": {
            "POLICY_BUCKET": policy_bucket,
            "POLICY_PREFIX": policy_prefix,
        },
    }

    # Pass Auth Provider name so external_tools.py can wrap with AuthenticatedFunctionTool
    if auth_provider_name:
        config_dict["env_vars"]["AUTH_PROVIDER_NAME"] = auth_provider_name

    # Pass OpenWeatherMap API Key as env var fallback
    # (Auth Manager injects as HTTP header, but OpenWeatherMap expects ?appid= query param)
    if openweather_api_key:
        config_dict["env_vars"]["OPENWEATHER_API_KEY"] = openweather_api_key

    # Debug: show what env_vars will be passed to Agent Engine
    print(f"  env_vars being passed to Agent Engine:")
    for k, v in config_dict["env_vars"].items():
        if "KEY" in k or "SECRET" in k:
            print(f"    {k} = ***{v[-4:] if len(v) > 4 else '***'}")
        else:
            print(f"    {k} = {v}")

    remote_app = client.agent_engines.create(
        agent=app,
        config=config_dict,
    )

    reasoning_engine = remote_app.api_resource.name
    principal = getattr(remote_app.api_resource, "identity", None)

    print("Deployed.")
    print(f"  reasoningEngine: {reasoning_engine}")
    if principal:
        print(f"  agent principal: {principal}")
    print()
    print("Next steps:")
    print(
        f"  1. Grant GCS access to the agent principal on gs://{policy_bucket}:"
    )
    print(
        "       gcloud storage buckets add-iam-policy-binding "
        f"gs://{policy_bucket} \\"
    )
    print("         --member=\"<principal from above>\" \\")
    print("         --role=\"roles/storage.objectViewer\"")
    print()
    print("  2. Register with Gemini Enterprise:")
    print(
        f"       REASONING_ENGINE={reasoning_engine} "
        "python register_gemini_enterprise.py"
    )


if __name__ == "__main__":
    main()
