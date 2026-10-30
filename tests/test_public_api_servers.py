import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from servers import open_meteo_weather, openstreetmap_overpass, wikidata_monuments


class PublicApiServerTests(unittest.IsolatedAsyncioTestCase):
    def make_client(self, data: dict[str, object]) -> tuple[MagicMock, MagicMock]:
        response = MagicMock()
        response.json.return_value = data
        response.raise_for_status.return_value = None

        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(return_value=response)
        client.post = AsyncMock(return_value=response)
        return client, response

    async def test_wikidata_country_search_returns_json_text(self) -> None:
        client, _ = self.make_client({"results": {"bindings": []}})

        with patch.object(wikidata_monuments.httpx, "AsyncClient", return_value=client) as factory:
            result = await wikidata_monuments.search_monuments_by_country("us")

        self.assertEqual(json.loads(result), {"results": {"bindings": []}})
        self.assertIn("P297", client.get.await_args.kwargs["params"]["query"])
        self.assertIn("P1435", client.get.await_args.kwargs["params"]["query"])
        self.assertIn("User-Agent", factory.call_args.kwargs["headers"])

    async def test_wikidata_nearby_search_validates_radius(self) -> None:
        with self.assertRaisesRegex(ValueError, "radius_km"):
            await wikidata_monuments.find_nearby_monuments(0, 0, 101)

    async def test_overpass_amenity_search_builds_bounded_query(self) -> None:
        client, _ = self.make_client({"elements": []})

        with patch.object(openstreetmap_overpass.httpx, "AsyncClient", return_value=client):
            result = await openstreetmap_overpass.get_amenities_nearby(51.5, -0.1, "cafe")

        self.assertEqual(json.loads(result), {"elements": []})
        query = client.post.await_args.kwargs["data"]["data"]
        self.assertIn("around:1000,51.5,-0.1", query)
        self.assertIn('["amenity"="cafe"]', query)

    async def test_overpass_rejects_query_injection(self) -> None:
        with self.assertRaisesRegex(ValueError, "amenity_type"):
            await openstreetmap_overpass.get_amenities_nearby(0, 0, 'cafe"];node;')

    async def test_open_meteo_requests_current_and_recent_historical_weather(self) -> None:
        client, _ = self.make_client({"current": {"temperature_2m": 10}})

        with patch.object(open_meteo_weather.httpx, "AsyncClient", return_value=client):
            result = await open_meteo_weather.get_historical_or_current_weather(40, -70)

        self.assertEqual(json.loads(result), {"current": {"temperature_2m": 10}})
        params = client.get.await_args.kwargs["params"]
        self.assertEqual(params["past_days"], 7)
        self.assertEqual(params["forecast_days"], 1)


if __name__ == "__main__":
    unittest.main()
