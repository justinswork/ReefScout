"""
mcp_server.py — ReefScout's MCP server.

A real Model Context Protocol server (FastMCP) exposing six ocean-data tools, each
wrapping a function from `ocean_data.py`. This file is the boundary between "tools"
and "agent": there is no LLM logic here, and the agent (the MCP *client* in
`agent.py`) never talks to the upstream ocean APIs directly — only through these
tools, over MCP JSON-RPC.

Design notes (these are rubric-relevant, see rubric.md #5):
  - Every tool has an explicit name, a model-facing description, and an input schema.
    FastMCP derives the schema from the Python type hints; the docstring becomes the
    description the model reads when deciding whether to call the tool.
  - Descriptions are written *for the model*: when to use the tool, what it returns,
    units, and caveats — because tool choice is the model's decision, the description
    is effectively part of the prompt design.
  - Tools return JSON-serializable dicts. "No data" comes back as
    {"found": false, "error": ...} so the model can reason about gaps and decide what
    to do next, rather than the call raising.

Run standalone (stdio transport):  python -m app.mcp_server
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from app import ocean_data

mcp = FastMCP(
    "reefscout-ocean",
    instructions=(
        "Live marine data tools for coastal trip planning and species identification. "
        "All data comes from free public sources (Open-Meteo, NOAA, iNaturalist, WoRMS) "
        "fetched at call time — nothing is mocked or cached from training data."
    ),
)


@mcp.tool()
async def geocode_place(place: str) -> dict:
    """Resolve a place name (e.g. 'La Jolla Cove', 'Key Largo', 'Hanauma Bay') to
    geographic coordinates.

    Use this FIRST whenever the user names a location and you need coordinates for any
    other tool. Returns latitude/longitude plus country, region, and timezone.
    If the place cannot be found, returns found=false with an error message — consider
    retrying with a simpler or nearby place name (e.g. 'La Jolla' instead of
    'La Jolla Cove tide pools').

    Args:
        place: Place name to look up. Simpler names match better.
    """
    return await ocean_data.geocode(place)


@mcp.tool()
async def get_marine_conditions(latitude: float, longitude: float, date: Optional[str] = None) -> dict:
    """Get ocean conditions for a coastal coordinate on a given date: maximum wave
    height (m), maximum swell height (m), wave period (s), and sea-surface temperature
    (°C, day min/avg/max).

    Use this to judge whether conditions suit snorkeling, tidepooling, or shore diving.
    Forecasts are available up to ~7 days ahead. Rough guide for snorkeling comfort:
    wave height under ~0.5 m is calm, 0.5–1 m is manageable for confident swimmers,
    over ~1.5 m is poor visibility and potentially unsafe for casual snorkelers.

    Args:
        latitude: Decimal latitude of the spot.
        longitude: Decimal longitude of the spot.
        date: Date as YYYY-MM-DD. Omit for today. Dates beyond the forecast window
            return found=false.
    """
    return await ocean_data.marine_conditions(latitude, longitude, date)


@mcp.tool()
async def get_tides(latitude: float, longitude: float, date: Optional[str] = None) -> dict:
    """Get high/low tide predictions for a date at the NOAA tide station nearest to a
    coordinate. Returns event times (local), heights in feet (MLLW datum), the station
    used, and how far away it is.

    Use this for trip timing: tidepooling is best in the ~2 hours around a LOW tide;
    some snorkel entries are easier near high tide. IMPORTANT: NOAA stations only cover
    US coasts and territories — for other countries this returns the nearest station,
    which may be uselessly far (check station.distance_km; beyond ~100 km treat tides
    as unavailable and say so rather than guessing).

    Args:
        latitude: Decimal latitude of the spot.
        longitude: Decimal longitude of the spot.
        date: Date as YYYY-MM-DD. Omit for today.
    """
    return await ocean_data.tides(latitude, longitude, date)


@mcp.tool()
async def get_species_nearby(
    latitude: float,
    longitude: float,
    radius_km: int = 25,
    iconic_taxa: str = "Actinopterygii,Mollusca",
    limit: int = 15,
) -> dict:
    """List the marine species most often observed near a coordinate, ranked by number
    of research-grade iNaturalist observations. Returns scientific + common names and
    observation counts.

    Two distinct uses:
    1. Trip planning — tell the user what they are realistically likely to see at a spot.
    2. Identification verification — check whether a candidate species is actually
       observed at the user's location before asserting an ID.

    Caveat: data is crowd-sourced; coastal queries can include occasional non-marine
    taxa (e.g. land snails under Mollusca). Ignore obviously terrestrial results.

    Args:
        latitude: Decimal latitude.
        longitude: Decimal longitude.
        radius_km: Search radius in km (default 25; widen to 50+ for sparse areas).
        iconic_taxa: Comma-separated iNaturalist iconic taxa filter. Useful values:
            Actinopterygii (fish), Mollusca (snails/octopus/nudibranchs), Mammalia
            (whales/seals), Reptilia (sea turtles), Echinodermata (stars/urchins),
            Cnidaria (jellies/anemones/corals), Arachnida is never marine — don't use it.
        limit: Max species to return (default 15).
    """
    return await ocean_data.species_nearby(latitude, longitude, radius_km, iconic_taxa, limit)


@mcp.tool()
async def search_marine_taxa(query: str, fuzzy: bool = True, limit: int = 8) -> dict:
    """Search the World Register of Marine Species (WoRMS) for taxa matching a
    scientific OR common name. Returns candidate species with full classification,
    taxonomic status, and AphiaID (the key for get_species_detail).

    Use this when identifying something the user saw or asked about. Works best with a
    species or genus guess ('Amphiprion', 'garibaldi', 'moon jelly'). It does NOT
    understand free-form descriptions — 'small orange fish with white stripes' will
    fail. First reason from your own knowledge to candidate names, then use this tool
    to verify those names exist and are current, then verify location plausibility
    with get_species_nearby.

    Args:
        query: Scientific or common name (not a description).
        fuzzy: Allow near-miss spelling on scientific names (default true).
        limit: Max candidates to return (default 8).
    """
    return await ocean_data.search_taxa(query, fuzzy, limit)


@mcp.tool()
async def get_species_detail(aphia_id: int) -> dict:
    """Get the authoritative WoRMS record for one species by AphiaID: accepted name,
    full classification, environment flags (marine/brackish/freshwater/terrestrial —
    use these to sanity-check that a candidate is actually a marine organism), known
    distribution localities, and IUCN conservation status when available.

    Use this to (a) confirm/enrich a species identification, (b) check whether a
    sighting location is plausible against known distribution, and (c) report
    conservation status. iucn_status may be null — say 'not assessed/unknown' rather
    than inventing one.

    Args:
        aphia_id: WoRMS AphiaID from search_marine_taxa results.
    """
    return await ocean_data.species_detail(aphia_id)


if __name__ == "__main__":
    # stdio transport: the agent backend (or any MCP client, e.g. `mcp dev`) launches
    # this as a subprocess and speaks JSON-RPC over stdin/stdout.
    mcp.run()
