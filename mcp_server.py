"""MCP server exposing OAC API-compatible query tooling."""
import json
import logging
from collections import OrderedDict

from classes.query_service import QueryService

try:
    from fastmcp import FastMCP
except Exception as exc:  # pragma: no cover - import guard for optional runtime
    raise RuntimeError(
        "fastmcp is required for MCP mode. Install dependencies from requirements.txt."
    ) from exc


LOGGER = logging.getLogger("oacapi.mcp")
SERVICE = QueryService()
MCP = FastMCP("OpenAstronomyCatalogAPI")


def _convert_payload(value):
    """Normalize ordered mappings into standard JSON-compatible structures."""
    if isinstance(value, OrderedDict):
        return {k: _convert_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_convert_payload(v) for v in value]
    if isinstance(value, dict):
        return {k: _convert_payload(v) for k, v in value.items()}
    return value


@MCP.tool
def query_api(
    catalog_name,
    event_name=None,
    quantity_name=None,
    attribute_name=None,
    params=None,
    method="GET",
):
    """Execute the same query semantics as the HTTP API.

    Args:
        catalog_name: Catalog route segment (e.g. `sne`, `catalog`, `all`).
        event_name: Optional event segment.
        quantity_name: Optional quantity segment.
        attribute_name: Optional attribute segment.
        params: Optional query parameter dict.
        method: HTTP-style method (`GET` or `POST`).
    """
    response = SERVICE.execute(
        catalog_name=catalog_name,
        event_name=event_name,
        quantity_name=quantity_name,
        attribute_name=attribute_name,
        params=params or {},
        method=method,
    )
    response["body"] = _convert_payload(response.get("body"))
    return response


@MCP.tool
def health():
    """Return basic MCP service health data."""
    return {"status": "ok", "service": "oacapi-mcp"}


@MCP.resource("oacapi://docs/signature")
def signature_reference():
    """Provide route signature guidance for clients."""
    return (
        "Route signature: /<catalog>/<event>/<quantity>/<attribute> "
        "with optional URL params. Use query_api tool arguments to map segments."
    )


@MCP.resource("oacapi://docs/query-example")
def query_example():
    """Provide a representative API query example."""
    return json.dumps(
        {
            "catalog_name": "sne",
            "event_name": "SN2014J",
            "quantity_name": "photometry",
            "attribute_name": "magnitude+band",
            "params": {"band": "B"},
            "method": "GET",
        },
        indent=2,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    LOGGER.info("Starting MCP server via stdio transport")
    MCP.run()
