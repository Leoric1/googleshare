"""Register the deployed ADK agent as an add-on agent in Gemini Enterprise.

This calls the Discovery Engine Assistants API directly. There is no Python
client helper for add-on agent registration at time of writing — the REST
surface is authoritative.

Usage:
  export GOOGLE_CLOUD_PROJECT=my-project
  export GEMINI_ENTERPRISE_APP_ID=my-app
  export REASONING_ENGINE=projects/.../locations/.../reasoningEngines/...
  python register_gemini_enterprise.py

Docs:
  https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing required env var: {name}")
    return value


def _access_token() -> str:
    result = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def main() -> None:
    project = _require("GOOGLE_CLOUD_PROJECT")
    app_id = _require("GEMINI_ENTERPRISE_APP_ID")
    reasoning_engine = _require("REASONING_ENGINE")
    endpoint_location = os.environ.get("GEMINI_ENTERPRISE_LOCATION", "global")
    display_name = os.environ.get("DISPLAY_NAME", "Policy Assistant")
    description = os.environ.get(
        "AGENT_DESCRIPTION",
        "Answers questions about internal organizational policies by retrieving "
        "documents from Google Cloud Storage. Invoke for questions about company "
        "rules, HR policies, security policies, acceptable use, or compliance.",
    )

    if endpoint_location == "global":
        host = "discoveryengine.googleapis.com"
    else:
        host = f"{endpoint_location}-discoveryengine.googleapis.com"

    url = (
        f"https://{host}/v1alpha/projects/{project}/locations/global/"
        f"collections/default_collection/engines/{app_id}/"
        "assistants/default_assistant/agents"
    )

    payload = {
        "displayName": display_name,
        "description": description,
        "adkAgentDefinition": {
            "provisionedReasoningEngine": {
                "reasoningEngine": reasoning_engine,
                "enableA2a": True,
            },
        },
    }

    icon_uri = os.environ.get("ICON_URI")
    if icon_uri:
        payload["icon"] = {"uri": icon_uri}

    auth_id = os.environ.get("TOOL_AUTHORIZATION")
    if auth_id:
        payload["authorizationConfig"] = {"toolAuthorizations": [auth_id]}

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {_access_token()}",
            "Content-Type": "application/json",
            "X-Goog-User-Project": project,
        },
    )

    with urllib.request.urlopen(req) as resp:
        response_body = resp.read().decode("utf-8")
        print(f"HTTP {resp.status}")
        print(response_body)


if __name__ == "__main__":
    main()
