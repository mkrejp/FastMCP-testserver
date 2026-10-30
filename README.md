# Universal MCP Aggregator

A single FastMCP host that starts configured MCP servers over stdio and forwards tool calls to them.

## Run

```sh
uv sync
uv run fastmcp run server.py --transport http --host 0.0.0.0 --port 8000
```

Open the forwarded port 8000 in Codespaces for the live dashboard. The MCP endpoint is available at `/mcp`. Keep the forwarded port private; the dashboard and MCP endpoint do not add authentication. The standard input/output server can still run directly with `uv run run-mcp`.

## Routing Configuration

Edit `mcp_routing_config.json`. Each entry under `managed_servers` has:

- `command`: executable to start (for example `uv` or `npx`)
- `args`: argv list passed directly to that executable; no shell is used
- `env`: string-to-string environment overrides; `${VARIABLE}` references are resolved from the host environment

Set referenced secrets in the Codespace environment before routing a call. Missing variables fail with a clear error; secret values are never written to the config. The `wikidata-monuments`, `openstreetmap-overpass`, and `open-meteo-weather` entries run the lightweight public-API bridges in `servers/`. They require no API keys. The Wikidata and Overpass bridges identify themselves with a User-Agent header; Overpass searches a fixed 1 km radius, and nearby Wikidata searches are limited to 100 km. Each bridge returns API results as JSON text in an MCP text result. The original `weather-service` and `github-service` entries are examples and require their configured downstream commands and credentials.

## Aggregator Tools

- `list_available_sub_tools()` returns configured server names.
- `route_mcp_call(server_name, tool_name, arguments)` starts the selected server, calls its named MCP tool over stdio, and returns the downstream MCP result.

Each routed call starts a fresh downstream process. Only trusted maintainers should edit the routing config: its commands are executed on the host running this aggregator.

## Dashboard

The dashboard displays configured launch commands, environment-variable names and presence, plus in-memory call counts and latency. It never displays environment values and redacts common credential arguments. Statistics reset when the aggregator restarts; the UI refreshes every five seconds.

## Development

```sh
uv run python -m unittest discover -s tests
```

See `AGENTS.md` for concise repository guidance and linked agent-specific instructions.