# Docker Compose deployment

This repository supports deploying the API and MCP server with Docker Compose.

## Services

- `api`: HTTP API (`wsgi:app`) with unchanged route signature.
- `mcp`: MCP layer exposing `query_api` and docs resources.
- `ingest` (profile): one-shot job to build `/data/oacapi.db` from static astrocatalog repos.

## Prerequisites

1. Docker and Docker Compose.
2. A local checkout of static astrocatalog repositories mounted at `./astrocats` (or set `AC_PATH`).

## Quick start

1. Copy environment defaults:

```bash
cp .env.example .env
```

2. Build the sqlite snapshot (required for `OAC_BACKEND=sqlite`):

```bash
docker compose --profile ingest run --rm ingest
```

The sqlite snapshot stores summary/index metadata and file pointers only. Full
event payloads are served directly from the mounted astrocatalog JSON files, so
the deployment does not create a second large copy of event data.

3. Start API and MCP services:

```bash
docker compose up --build -d api mcp
```

4. Verify API:

```bash
curl "http://localhost:5000/"
```

## Memory notes

Compose includes per-service memory caps intended for constrained hosts:

- `api`: `640m`
- `mcp`: `256m`
- `ingest`: `768m` (one-shot profile)

Tune these values in `docker-compose.yml` if your host constraints differ.

