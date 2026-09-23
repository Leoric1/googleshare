"""Send a live query to the deployed Agent Engine reasoning engine."""

from __future__ import annotations

import asyncio
import os
import sys

import vertexai


async def main(prompt: str) -> None:
    project = os.environ["GOOGLE_CLOUD_PROJECT"]
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    resource = os.environ["REASONING_ENGINE"]

    client = vertexai.Client(
        project=project,
        location=location,
        http_options=dict(api_version="v1beta1"),
    )
    remote = client.agent_engines.get(name=resource)

    session = await remote.async_create_session(user_id="smoke-test")
    async for event in remote.async_stream_query(
        user_id="smoke-test",
        session_id=session["id"],
        message=prompt,
    ):
        parts = (event.get("content") or {}).get("parts", [])
        for p in parts:
            if "text" in p:
                print(p["text"], end="", flush=True)
    print()


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) or "List the available policy documents."
    asyncio.run(main(prompt))
