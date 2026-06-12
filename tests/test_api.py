"""
Tests for the FastAPI layer: the taxon-group mapping (pure) and the /species/resolve
endpoint that auto-enriches a logbook sighting from just a name.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import _derive_group, app


def test_derive_group_maps_classifications():
    assert _derive_group({"phylum": "Mollusca"}) == "mollusk"
    assert _derive_group({"phylum": "Arthropoda"}) == "crustacean"
    assert _derive_group({"phylum": "Echinodermata"}) == "echinoderm"
    assert _derive_group({"phylum": "Cnidaria"}) == "cnidarian"
    assert _derive_group({"phylum": "Chordata", "class": "Teleostei"}) == "fish"
    assert _derive_group({"phylum": "Chordata", "class": "Elasmobranchii"}) == "shark_ray"
    assert _derive_group({"phylum": "Chordata", "class": "Reptilia", "order": "Testudines"}) == "turtle"
    assert _derive_group({"phylum": "Chordata", "class": "Mammalia"}) == "mammal"
    assert _derive_group({"phylum": "Chordata", "class": "Aves"}) == "seabird"
    assert _derive_group({}) == "other"


@pytest.mark.live
async def test_resolve_endpoint_enriches_from_common_name():
    # ASGITransport calls the app in-process without triggering the lifespan, so the
    # agent/MCP don't start — /species/resolve only needs the (keyless) WoRMS lookup.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/species/resolve", params={"name": "garibaldi"})
    data = r.json()
    assert data["found"] is True
    assert data["scientific_name"] == "Hypsypops rubicundus"
    assert data["group"] == "fish"


@pytest.mark.live
async def test_resolve_endpoint_unknown_name():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/species/resolve", params={"name": "zzzqqx-not-real"})
    assert r.json()["found"] is False
