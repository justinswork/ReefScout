"""
MCP server tests: connect to app/mcp_server.py over real stdio JSON-RPC (the same
transport the agent backend uses), verify all six tools are exposed with schemas,
and execute one tool end-to-end through the protocol.
"""

import json
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.live

EXPECTED_TOOLS = {
    "geocode_place",
    "get_marine_conditions",
    "get_tides",
    "get_species_nearby",
    "search_marine_taxa",
    "get_species_detail",
}

SERVER_PARAMS = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"])


async def test_server_exposes_six_tools_with_schemas():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools

            names = {t.name for t in tools}
            assert names == EXPECTED_TOOLS

            for t in tools:
                # Rubric #5: every tool must carry a description and an input schema.
                assert t.description and len(t.description) > 40, f"{t.name} lacks a real description"
                assert t.inputSchema.get("type") == "object"

            # Spot-check one schema's required params.
            geo = next(t for t in tools if t.name == "geocode_place")
            assert "place" in geo.inputSchema["properties"]
            assert "place" in geo.inputSchema.get("required", [])


async def test_tool_executes_over_mcp():
    async with stdio_client(SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("geocode_place", {"place": "Key Largo"})

            assert not result.isError
            payload = json.loads(result.content[0].text)
            assert payload["found"] is True
            assert abs(payload["latitude"] - 25.1) < 1.0
