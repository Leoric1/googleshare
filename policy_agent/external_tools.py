"""External API tools demonstrating Auth Manager transparent injection.

These tools call external APIs (OpenWeatherMap) that require API key
authentication. The API key is stored in Agent Identity Auth Manager and
injected at runtime by ADK's AuthenticatedFunctionTool — the function
body contains ZERO authentication code.

Contrast with the traditional approach (AWS-style decorator injection):

  # GCP transparent interception — function body has zero auth code
  async def get_weather(lat, lon):
      response = await client.get("https://api.openweathermap.org/...")
      return response.json()

  get_weather_tool = AuthenticatedFunctionTool(func=get_weather, auth_config=auth_config)

  # Traditional — 3 lines of auth boilerplate inside the function
  @requires_access_token(provider="my-provider")
  async def get_weather(lat, lon):
      token = get_token_from_context()               # ← must fetch token
      headers = {"X-Api-Key": token}                 # ← must build header
      response = await client.get(url, headers=headers)  # ← must pass header
      return response.json()

All tools return a dict. On failure they return a structured error dict,
same convention as gcs_tools.py.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any

from . import config


def get_weather(city: str) -> dict[str, Any]:
    """Get current weather conditions for a city from OpenWeatherMap.

    The API key (appid) is injected by ADK's AuthenticatedFunctionTool
    at runtime via Agent Identity Auth Manager. This function body
    contains no authentication code whatsoever.

    Args:
      city: City name, e.g. "London", "Beijing", or "San Francisco,CA".

    Returns:
      On success: {city, temperature_c, condition, humidity, wind_speed, raw}.
      On failure: {error, message} with a human-readable explanation.
    """
    base_url = config.EXTERNAL_API_URL

    # Auth Manager transparently injects API Key as HTTP header.
    # OpenWeatherMap expects ?appid= as query param, so we also check
    # the env var fallback (set by deploy.py via Auth Manager integration).
    params = {"q": city, "units": "metric"}

    # Fallback: read API key from env var if Auth Manager didn't inject it
    api_key = os.environ.get("OPENWEATHER_API_KEY", "")
    if api_key:
        params["appid"] = api_key

    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_string}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {
            "city": data.get("name", city),
            "temperature_c": data["main"]["temp"],
            "condition": data["weather"][0]["description"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
            "raw": data,
        }
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {
                "error": "unauthenticated",
                "message": (
                    f"OpenWeatherMap rejected the request for '{city}' — "
                    "API key missing or invalid. If running locally without "
                    "Auth Manager, the weather tool is not available."
                ),
                "remediation": (
                    "Ensure the Auth Provider is created and the agent is "
                    "deployed with AuthenticatedFunctionTool wrapping."
                ),
            }
        return {
            "error": "api_error",
            "message": f"OpenWeatherMap returned HTTP {e.code} for '{city}': {e.reason}",
        }
    except Exception as e:
        return {
            "error": "unexpected",
            "message": f"Failed to get weather for '{city}': {type(e).__name__}: {e}",
        }


# ── Wrap with AuthenticatedFunctionTool if ADK supports it ──────────────────
# This is the production path: ADK intercepts the HTTP request and injects
# the API key from Auth Manager. The function above never touches the key.

_auth_provider = config.AUTH_PROVIDER_NAME

try:
    from google.adk.tools import AuthenticatedFunctionTool  # type: ignore
    from google.adk.auth import AuthConfig, GcpAuthProviderScheme  # type: ignore

    if _auth_provider:
        _auth_config = AuthConfig(
            auth_scheme=GcpAuthProviderScheme(name=_auth_provider)
        )
        get_weather_tool = AuthenticatedFunctionTool(
            func=get_weather,
            auth_config=_auth_config,
        )
    else:
        # Auth Provider not configured — use raw function (local testing only)
        get_weather_tool = get_weather
except ImportError:
    # ADK version doesn't support AuthenticatedFunctionTool yet.
    # Fall back to raw function — works for local testing, but without
    # transparent credential injection. API key read from env var fallback.
    get_weather_tool = get_weather
