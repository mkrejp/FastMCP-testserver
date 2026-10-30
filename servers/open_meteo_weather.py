import json
import math

import httpx
from fastmcp import FastMCP

mcp = FastMCP("open-meteo-weather")
FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"
HEADERS = {"User-Agent": "FastMCP-Testserver/0.1 (Open-Meteo weather lookup)"}


@mcp.tool()
async def get_historical_or_current_weather(
    latitude: float,
    longitude: float,
) -> str:
    """Get current weather and hourly observations/forecast spanning the past 7 days."""
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90.")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180.")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,"
            "is_day,precipitation,weather_code,wind_speed_10m"
        ),
        "hourly": "temperature_2m,precipitation_probability,precipitation",
        "past_days": 7,
        "forecast_days": 1,
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=30, headers=HEADERS) as client:
        response = await client.get(FORECAST_ENDPOINT, params=params)
        response.raise_for_status()
    return json.dumps(response.json(), ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
