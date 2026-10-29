# Universal MCP Aggregator

A single FastMCP host that starts configured MCP servers over stdio and forwards tool calls to them.

## Run

```sh
uv sync
uv run fastmcp dev inspector server.py
```

FastMCP Inspector opens a local UI for connecting to the aggregator. The same server can run directly with `uv run run-mcp`.

## Routing Configuration

Edit `mcp_routing_config.json`. Each entry under `managed_servers` has:

- `command`: executable to start (for example `uv` or `npx`)
- `args`: argv list passed directly to that executable; no shell is used
- `env`: string-to-string environment overrides; `${VARIABLE}` references are resolved from the host environment

Set referenced secrets in the Codespace environment before routing a call. Missing variables fail with a clear error; secret values are never written to the config. The sample server commands are placeholders and must be replaced with actual MCP server commands and arguments.

## Aggregator Tools

- `list_available_sub_tools()` returns configured server names.
- `route_mcp_call(server_name, tool_name, arguments)` starts the selected server, calls its named MCP tool over stdio, and returns the downstream MCP result.

Each routed call starts a fresh downstream process. Only trusted maintainers should edit the routing config: its commands are executed on the host running this aggregator.

## Development

```sh
uv run python -m unittest discover -s tests
```

See `AGENTS.md` for concise repository guidance and linked agent-specific instructions.