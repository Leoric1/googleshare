"""Local smoke test for the policy agent.

Uses your local ADC (gcloud auth application-default login) to exercise the
GCS tools — the Agent Identity principal is only minted once the agent runs
inside Vertex AI Agent Engine.

Usage:
  export GOOGLE_CLOUD_PROJECT=my-project
  export POLICY_BUCKET=my-policy-docs
  python local_run.py "what is our data retention policy?"
"""

from __future__ import annotations

import asyncio
import sys

from google.adk.runners import InMemoryRunner
from google.genai import types

from policy_agent.agent import root_agent


async def _run(prompt: str) -> None:
    runner = InMemoryRunner(agent=root_agent, app_name="policy-agent-local")
    session = await runner.session_service.create_session(
        app_name="policy-agent-local", user_id="local-user"
    )
    async for event in runner.run_async(
        user_id="local-user",
        session_id=session.id,
        new_message=types.Content(
            role="user", parts=[types.Part(text=prompt)]
        ),
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(part.text, end="", flush=True)
    print()


def main() -> None:
    prompt = " ".join(sys.argv[1:]) or "List the available policy documents."
    asyncio.run(_run(prompt))


if __name__ == "__main__":
    main()
