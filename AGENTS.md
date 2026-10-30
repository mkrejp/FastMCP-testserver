# Agent Guide

- Read `README.md` for setup, routing behavior, and security constraints.
- System architecture: `docs/ARCHITECTURE.md`. Network paths and trust boundaries: `docs/CONNECTIVITY.md`.
- `server.py` implements the aggregator; `mcp_routing_config.json` is the downstream process registry.
- Keep `args` as an argv list and `env` as string values. Use `${VARIABLE}` for secrets; never commit real credentials.
- Run `uv sync` and `uv run python -m unittest discover -s tests` after routing changes.
- Routing config commands execute locally. Do not treat untrusted config as data-only input.
- Keep this file short; Claude Code and Cursor entry points reference it.