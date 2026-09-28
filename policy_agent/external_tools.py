"""External API tools demonstrating Auth Manager transparent injection.

These tools call external APIs (API Ninjas) that require API key
authentication via HTTP header (X-Api-Key). The API key is stored in
Agent Identity Auth Manager and injected at runtime by ADK's
AuthenticatedFunctionTool — the function body contains ZERO authentication code.

Contrast with the traditional approach (AWS-style decorator injection):

  # GCP transparent interception — function body has zero auth code
  def get_weather(city):
      url = f'https://api.api-ninjas.com/v1/weather?name={city}'
      req = urllib.request.Request(url)
      with urllib.request.urlopen(req) as resp:
          return json.loads(resp.read())

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
import urllib.parse
import urllib.request
from typing import Any

from . import config


def get_weather(city: str) -> dict[str, Any]:
    """Get current weather conditions for a city from API Ninjas Weather API.

    The API key is injected by ADK's AuthenticatedFunctionTool at runtime
    via Agent Identity Auth Manager as the X-Api-Key HTTP header.
    This function body contains no authentication code whatsoever.

    API Ninjas free tier requires lat/lon for the Weather endpoint,
    so we first look up the city coordinates via the City endpoint,
    then query the Weather endpoint with those coordinates.

    Args:
      city: City name, e.g. "London", "Beijing", or "San Francisco,CA".

    Returns:
      On success: {city, temperature_c, condition, humidity, wind_speed, raw}.
      On failure: {error, message} with a human-readable explanation.
    """
    base_url = config.EXTERNAL_API_URL  # https://api.api-ninjas.com/v1/weather

    # Step 1: Look up city coordinates via City API
    city_url = f"https://api.api-ninjas.com/v1/city?{urllib.parse.urlencode({'name': city})}"
    try:
        city_req = urllib.request.Request(city_url)
        with urllib.request.urlopen(city_req) as city_resp:
            city_data = json.loads(city_resp.read().decode("utf-8"))
        if not city_data:
            return {"error": "not_found", "message": f"City '{city}' not found."}
        lat = city_data[0]["latitude"]
        lon = city_data[0]["longitude"]
    except Exception as e:
        return {"error": "unexpected", "message": f"City lookup failed for '{city}': {type(e).__name__}: {e}"}

    # Step 2: Query weather with coordinates
    params = urllib.parse.urlencode({"lat": lat, "lon": lon})
    url = f"{base_url}?{params}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {
            "city": city,
            "temperature_c": data.get("temp"),
            "condition": data.get("weather_description", "unknown"),
            "humidity": data.get("humidity"),
            "wind_speed": data.get("wind_speed"),
            "raw": data,
        }
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return {
                "error": "unauthenticated",
                "message": (
                    f"API Ninjas rejected the request for '{city}' — "
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
            "message": f"API Ninjas returned HTTP {e.code} for '{city}': {e.reason}",
        }
    except Exception as e:
        return {
            "error": "unexpected",
            "message": f"Failed to get weather for '{city}': {type(e).__name__}: {e}",
        }


# ── Wrap with AuthenticatedFunctionTool if ADK supports it ──────────────────
# This is the production path: ADK intercepts the HTTP request and injects
# the API key from Auth Manager as the X-Api-Key header.
# The function above never touches the key.

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
    # transparent credential injection.
    get_weather_tool = get_weather
