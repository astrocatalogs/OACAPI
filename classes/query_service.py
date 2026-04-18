"""Service wrapper to call API logic from HTTP and MCP layers."""
from collections import OrderedDict

from flask import Response


class QueryService(object):
    """Programmatic query facade preserving API behavior."""

    def __init__(self):
        # Import lazily to avoid module-import cycles during app bootstrap.
        from api import Catalog  # pylint: disable=import-outside-toplevel

        self._resource = Catalog()

    def execute(
        self,
        catalog_name,
        event_name=None,
        quantity_name=None,
        attribute_name=None,
        params=None,
        method="GET",
    ):
        """Execute API query and return structured result payload."""
        params = params or {}
        from api import app  # pylint: disable=import-outside-toplevel

        upper_method = method.upper()
        with app.test_request_context(
            method=upper_method,
            path="/",
            json=params if upper_method == "POST" else None,
            query_string=None if upper_method == "POST" else params,
        ):
            result = self._resource.get(
                catalog_name, event_name=event_name, quantity_name=quantity_name, attribute_name=attribute_name
            )

        if isinstance(result, Response):
            return {
                "kind": "response",
                "status": result.status_code,
                "mimetype": result.mimetype,
                "body": result.get_data(as_text=True),
            }
        if isinstance(result, OrderedDict):
            return {"kind": "json", "status": 200, "body": result}
        if isinstance(result, dict):
            return {"kind": "json", "status": 200, "body": result}
        if isinstance(result, list):
            return {"kind": "json", "status": 200, "body": result}
        return {"kind": "raw", "status": 200, "body": result}
