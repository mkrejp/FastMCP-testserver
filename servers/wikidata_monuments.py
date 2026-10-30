import json
import math
import re
from typing import Any

import httpx
from fastmcp import FastMCP

mcp = FastMCP("wikidata-monuments")
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
HEADERS = {
    "Accept": "application/sparql-results+json",
    "User-Agent": "FastMCP-Testserver/0.1 (public cultural heritage lookup)",
}
COUNTRY_CODE = re.compile(r"^[A-Za-z]{2}$")


def _validate_coordinates(latitude: float, longitude: float) -> None:
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90.")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180.")


async def _query_wikidata(query: str) -> str:
    async with httpx.AsyncClient(timeout=30, headers=HEADERS) as client:
        response = await client.get(SPARQL_ENDPOINT, params={"query": query})
        response.raise_for_status()
    return json.dumps(response.json(), ensure_ascii=False)


@mcp.tool()
async def search_monuments_by_country(country_code: str) -> str:
    """Find up to 100 Wikidata places with heritage designations in a country."""
    if not COUNTRY_CODE.fullmatch(country_code):
        raise ValueError("country_code must be a two-letter ISO 3166-1 alpha-2 code.")

    query = f"""
    SELECT ?item ?itemLabel ?itemDescription ?coordinate WHERE {{
      ?country wdt:P297 "{country_code.upper()}".
      ?item wdt:P17 ?country;
            wdt:P625 ?coordinate;
            wdt:P1435 ?designation.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    ORDER BY ?itemLabel
    LIMIT 100
    """
    return await _query_wikidata(query)


@mcp.tool()
async def find_nearby_monuments(
    latitude: float,
    longitude: float,
    radius_km: float,
) -> str:
    """Find up to 100 heritage-designated Wikidata places within 100 km."""
    _validate_coordinates(latitude, longitude)
    if not math.isfinite(radius_km) or not 0 < radius_km <= 100:
        raise ValueError("radius_km must be greater than 0 and no more than 100.")

    query = f"""
    SELECT ?item ?itemLabel ?itemDescription ?coordinate ?distance WHERE {{
      SERVICE wikibase:around {{
        ?item wdt:P625 ?coordinate.
        bd:serviceParam wikibase:center
          "Point({longitude} {latitude})"^^geo:wktLiteral.
        bd:serviceParam wikibase:radius "{radius_km}".
        bd:serviceParam wikibase:distance ?distance.
      }}
      ?item wdt:P1435 ?designation.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    ORDER BY ?distance
    LIMIT 100
    """
    return await _query_wikidata(query)


if __name__ == "__main__":
    mcp.run()
