import json
import math
import re

import httpx
from fastmcp import FastMCP

mcp = FastMCP("openstreetmap-overpass")
OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "FastMCP-Testserver/0.1 (public OpenStreetMap lookup)",
}
AMENITY_VALUE = re.compile(r"^[A-Za-z0-9 _-]{1,64}$")
SEARCH_RADIUS_METERS = 1000


def _validate_coordinates(latitude: float, longitude: float) -> None:
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90.")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180.")


@mcp.tool()
async def get_amenities_nearby(
    latitude: float,
    longitude: float,
    amenity_type: str,
) -> str:
    """Find OpenStreetMap amenities of the requested type within 1 km."""
    _validate_coordinates(latitude, longitude)
    if not AMENITY_VALUE.fullmatch(amenity_type):
        raise ValueError("amenity_type must be 1-64 letters, numbers, spaces, '_' or '-'.")

    query = (
        f'[out:json][timeout:25];'
        f'nwr(around:{SEARCH_RADIUS_METERS},{latitude},{longitude})'
        f'["amenity"="{amenity_type}"];out center;'
    )
    async with httpx.AsyncClient(timeout=35, headers=HEADERS) as client:
        response = await client.post(OVERPASS_ENDPOINT, data={"data": query})
        response.raise_for_status()
    return json.dumps(response.json(), ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
