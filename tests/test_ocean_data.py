"""
Live integration tests for the ocean_data layer.

These hit the real, free, no-key APIs (marked ``live``) — they are how we verify that an
upstream endpoint hasn't changed shape or gone down. Run with:  pytest -m live

They assert structure and plausibility, not exact values (live data shifts daily).
"""

import pytest

from app import ocean_data as od

pytestmark = pytest.mark.live

# A coordinate we know is well-sampled: La Jolla Cove, CA.
LA_JOLLA = (32.85, -117.27)
# A clownfish — a species with rich WoRMS data — for taxonomy tests.
CLOWNFISH_APHIA = 278400  # Amphiprion ocellaris


async def test_geocode_resolves_known_place():
    r = await od.geocode("La Jolla")
    assert r["found"] is True
    assert abs(r["latitude"] - 32.85) < 1.0
    assert abs(r["longitude"] - (-117.27)) < 1.0


async def test_geocode_handles_nonsense():
    r = await od.geocode("zzzzqqqx-not-a-place")
    assert r["found"] is False
    assert "error" in r


async def test_marine_conditions_shape():
    r = await od.marine_conditions(*LA_JOLLA)
    assert r["found"] is True
    assert r["wave_height_max"]["unit"] == "m"
    # Wave height should be a non-negative number when present.
    wh = r["wave_height_max"]["value"]
    assert wh is None or wh >= 0


async def test_tides_returns_hilo_events():
    r = await od.tides(*LA_JOLLA)
    assert r["found"] is True
    assert r["station"]["distance_km"] < 100  # La Jolla has a station very close
    assert all(e["type"] in ("high", "low") for e in r["events"])


async def test_species_nearby_returns_ranked_species():
    r = await od.species_nearby(*LA_JOLLA, radius_km=25, limit=5)
    assert r["found"] is True
    assert len(r["species"]) > 0
    # Results should be ranked by observation count (descending).
    counts = [s["observations"] for s in r["species"]]
    assert counts == sorted(counts, reverse=True)


async def test_search_taxa_scientific_name():
    r = await od.search_taxa("Amphiprion ocellaris", fuzzy=False)
    assert r["found"] is True
    names = [c["scientific_name"] for c in r["candidates"]]
    assert any("Amphiprion ocellaris" == n for n in names)


async def test_search_taxa_common_name_fallback():
    r = await od.search_taxa("clownfish")
    # Vernacular search should surface at least one Amphiprion-family candidate.
    assert r["found"] is True
    assert len(r["candidates"]) > 0


async def test_species_detail_has_environment_flags():
    r = await od.species_detail(CLOWNFISH_APHIA)
    assert r["found"] is True
    assert r["scientific_name"] == "Amphiprion ocellaris"
    assert r["environment"]["is_marine"] in (0, 1, True, False, None)
