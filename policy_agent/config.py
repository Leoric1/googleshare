import os

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

POLICY_BUCKET = os.environ.get("POLICY_BUCKET", "")
POLICY_PREFIX = os.environ.get("POLICY_PREFIX", "policies/")

MODEL = os.environ.get("AGENT_MODEL", "gemini-2.5-flash")

MAX_DOC_BYTES = int(os.environ.get("MAX_DOC_BYTES", str(2 * 1024 * 1024)))

# ── External API (OpenWeatherMap) ──────────────────────────────────────────
# The API key is NOT here — it lives in Agent Identity Auth Manager.
# ADK's AuthenticatedFunctionTool injects it at runtime.
EXTERNAL_API_URL = os.environ.get(
    "EXTERNAL_API_URL",
    "https://api.openweathermap.org/data/2.5/weather",
)

# Auth Manager — Auth Provider resource name (created via gcloud)
AUTH_PROVIDER_NAME = os.environ.get("AUTH_PROVIDER_NAME", "")
