"""
ocean_data.py — ReefScout's live data layer.

Plain async functions that fetch real marine data from free, no-API-key sources and
normalize each response into a clean Python dict. There is **no LLM logic in this file** —
it is purely the "tools' hands": fetch, normalize, and report gaps honestly so the agent
upstream can reason about them.

Sources (all free, no key required):
  - Open-Meteo Geocoding   https://open-meteo.com/en/docs/geocoding-api
  - Open-Meteo Marine      https://open-meteo.com/en/docs/marine-weather-api
  - NOAA CO-OPS            https://api.tidesandcurrents.noaa.gov/
  - iNaturalist            https://api.inaturalist.org/v1/docs/
  - WoRMS REST            https://www.marinespecies.org/rest/

Convention: every public function returns a dict. Success includes ``"found": True``;
failure or "no data" returns ``"found": False`` with a human-readable ``"error"`` rather
than raising, so the agent can decide what to do instead of the request crashing.
"""

from __future__ import annotations

import math
from datetime import date as _date
from typing import Any, Optional
from urllib.parse import quote

import httpx

# --- Endpoints -------------------------------------------------------------------------
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
NOAA_DATA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NOAA_STATIONS_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
INAT_SPECIES_COUNTS_URL = "https://api.inaturalist.org/v1/observations/species_counts"
INAT_TAXA_URL = "https://api.inaturalist.org/v1/taxa"
WORMS_BASE = "https://www.marinespecies.org/rest"

# Polite identification + sane timeout so a slow upstream can't hang the agent.
_HEADERS = {"User-Agent": "ReefScout/0.1 (educational capstone; contact via GitHub justinswork/ReefScout)"}
_TIMEOUT = httpx.Timeout(15.0, connect=10.0)

# NOAA's full tide-prediction station list (~3,450 stations) is fetched once and cached
# in-process; we compute the nearest station ourselves rather than per-request downloads.
_STATION_CACHE: Optional[list[dict]] = None


# --- HTTP helper -----------------------------------------------------------------------
async def _get_json(url: str, params: Optional[dict] = None, *, allow_empty: bool = False) -> Any:
    """GET a URL and parse JSON. Returns ``None`` on an empty body when ``allow_empty`` is
    set (WoRMS replies 204/empty for "no match"). Raises on transport/HTTP errors so the
    public functions can catch and normalize them."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        if allow_empty and not resp.content:
            return None
        return resp.json()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# --- 1. Geocoding ----------------------------------------------------------------------
async def geocode(place: str) -> dict:
    """Resolve a place name to coordinates via Open-Meteo Geocoding."""
    try:
        data = await _get_json(GEOCODE_URL, {"name": place, "count": 1, "language": "en"})
    except Exception as exc:  # noqa: BLE001 - normalize all upstream failures
        return {"found": False, "query": place, "error": f"Geocoding request failed: {exc}"}

    results = data.get("results") if isinstance(data, dict) else None
    if not results:
        return {"found": False, "query": place, "error": f"No location found for '{place}'."}

    r = results[0]
    return {
        "found": True,
        "query": place,
        "name": r.get("name"),
        "latitude": r.get("latitude"),
        "longitude": r.get("longitude"),
        "country": r.get("country"),
        "region": r.get("admin1"),
        "timezone": r.get("timezone"),
    }


# --- 2. Marine conditions --------------------------------------------------------------
async def marine_conditions(latitude: float, longitude: float, date: Optional[str] = None) -> dict:
    """Wave height, swell, period, and sea-surface temperature for a coordinate and date
    (``YYYY-MM-DD``; defaults to today). Daily maxima + the day's average SST."""
    params: dict[str, Any] = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "wave_height_max,wave_period_max,swell_wave_height_max",
        "hourly": "sea_surface_temperature",
        "timezone": "auto",
    }
    if date:
        params["start_date"] = date
        params["end_date"] = date
    else:
        params["forecast_days"] = 1

    try:
        data = await _get_json(MARINE_URL, params)
    except Exception as exc:  # noqa: BLE001
        return {"found": False, "error": f"Marine conditions request failed: {exc}"}

    if not isinstance(data, dict) or data.get("error"):
        reason = data.get("reason") if isinstance(data, dict) else "unknown"
        return {"found": False, "error": f"Marine API error: {reason}"}

    daily = data.get("daily", {})
    times = daily.get("time") or []
    if not times:
        return {"found": False, "error": "No marine forecast available for that date/location."}

    def _first(key: str):
        vals = daily.get(key) or []
        return vals[0] if vals else None

    sst_vals = [v for v in data.get("hourly", {}).get("sea_surface_temperature", []) if v is not None]
    sst = None
    if sst_vals:
        sst = {
            "avg": round(sum(sst_vals) / len(sst_vals), 1),
            "min": round(min(sst_vals), 1),
            "max": round(max(sst_vals), 1),
            "unit": "°C",
        }

    return {
        "found": True,
        "location": {"latitude": latitude, "longitude": longitude},
        "date": times[0],
        "wave_height_max": {"value": _first("wave_height_max"), "unit": "m"},
        "swell_height_max": {"value": _first("swell_wave_height_max"), "unit": "m"},
        "wave_period_max": {"value": _first("wave_period_max"), "unit": "s"},
        "sea_surface_temperature": sst,
        "source": "Open-Meteo Marine",
    }


# --- 3. Tides --------------------------------------------------------------------------
async def _load_stations() -> list[dict]:
    global _STATION_CACHE
    if _STATION_CACHE is None:
        data = await _get_json(NOAA_STATIONS_URL, {"type": "tidepredictions"})
        _STATION_CACHE = [
            {"id": s["id"], "name": s.get("name"), "lat": s.get("lat"), "lng": s.get("lng"), "state": s.get("state")}
            for s in data.get("stations", [])
            if s.get("lat") is not None and s.get("lng") is not None
        ]
    return _STATION_CACHE


async def _nearest_tide_station(latitude: float, longitude: float) -> Optional[dict]:
    stations = await _load_stations()
    best, best_d = None, float("inf")
    for s in stations:
        d = _haversine_km(latitude, longitude, s["lat"], s["lng"])
        if d < best_d:
            best, best_d = s, d
    if best is None:
        return None
    out = dict(best)
    out["distance_km"] = round(best_d, 1)
    return out


async def tides(latitude: float, longitude: float, date: Optional[str] = None) -> dict:
    """High/low tide predictions for the date (``YYYY-MM-DD``, default today) at the NOAA
    tide station nearest to the coordinate. Heights are feet relative to MLLW."""
    target = date or _date.today().isoformat()
    try:
        station = await _nearest_tide_station(latitude, longitude)
    except Exception as exc:  # noqa: BLE001
        return {"found": False, "error": f"Could not load NOAA station list: {exc}"}
    if station is None:
        return {"found": False, "error": "No NOAA tide station could be located."}

    ymd = target.replace("-", "")
    params = {
        "product": "predictions",
        "application": "ReefScout",
        "begin_date": ymd,
        "end_date": ymd,
        "datum": "MLLW",
        "station": station["id"],
        "time_zone": "lst_ldt",
        "units": "english",
        "interval": "hilo",
        "format": "json",
    }
    try:
        data = await _get_json(NOAA_DATA_URL, params)
    except Exception as exc:  # noqa: BLE001
        return {"found": False, "error": f"Tide prediction request failed: {exc}"}

    if isinstance(data, dict) and data.get("error"):
        return {"found": False, "error": f"NOAA error: {data['error'].get('message', 'unknown')}"}

    preds = data.get("predictions", []) if isinstance(data, dict) else []
    events = [
        {"time": p["t"], "height_ft": float(p["v"]), "type": "high" if p["type"] == "H" else "low"}
        for p in preds
    ]
    return {
        "found": bool(events),
        "date": target,
        "datum": "MLLW",
        "units": "feet",
        "station": {"id": station["id"], "name": station["name"], "distance_km": station["distance_km"]},
        "events": events,
        "note": (
            f"Nearest tide station is {station['distance_km']} km away"
            + ("; tides may differ at your exact spot." if station["distance_km"] > 30 else ".")
        ),
        "source": "NOAA CO-OPS",
    }


# --- 4. Species nearby (what you'll likely see) ----------------------------------------
async def species_nearby(
    latitude: float,
    longitude: float,
    radius_km: int = 25,
    iconic_taxa: str = "Actinopterygii,Mollusca",
    limit: int = 15,
) -> dict:
    """Most-observed marine species near a coordinate, from iNaturalist research-grade
    observations. NOTE: iNaturalist has no strict marine filter, so coastal queries can
    include a few terrestrial taxa (e.g. land snails under ``Mollusca``) — the caller
    should sanity-check obvious non-marine results."""
    params = {
        "lat": latitude,
        "lng": longitude,
        "radius": radius_km,
        "iconic_taxa": iconic_taxa,
        "quality_grade": "research",
        "per_page": limit,
        "locale": "en",
    }
    try:
        data = await _get_json(INAT_SPECIES_COUNTS_URL, params)
    except Exception as exc:  # noqa: BLE001
        return {"found": False, "error": f"iNaturalist request failed: {exc}"}

    results = data.get("results", []) if isinstance(data, dict) else []
    species = []
    for r in results:
        t = r.get("taxon", {})
        species.append(
            {
                "scientific_name": t.get("name"),
                "common_name": t.get("preferred_common_name"),
                "observations": r.get("count"),
                "rank": t.get("rank"),
                "inat_taxon_id": t.get("id"),
            }
        )
    return {
        "found": bool(species),
        "location": {"latitude": latitude, "longitude": longitude, "radius_km": radius_km},
        "distinct_species_in_area": data.get("total_results") if isinstance(data, dict) else None,
        "species": species,
        "note": "Ranked by number of research-grade iNaturalist observations. May include occasional non-marine taxa near shore.",
        "source": "iNaturalist",
    }


# --- 4b. Species reference images -------------------------------------------------------
async def species_images(species: str, limit: int = 3) -> dict:
    """Curated reference photos for a species (or close matches) from iNaturalist's
    taxon database. Returns photo URLs plus attribution — attribution must be shown
    when a photo is displayed."""
    params = {"q": species, "per_page": max(limit, 3), "locale": "en"}
    try:
        data = await _get_json(INAT_TAXA_URL, params)
    except Exception as exc:  # noqa: BLE001
        return {"found": False, "query": species, "error": f"iNaturalist taxa request failed: {exc}"}

    results = data.get("results", []) if isinstance(data, dict) else []
    matches = []
    # iNaturalist fuzzy-matches names, so a bare genus like "Aurelia" can surface insects
    # or plants ahead of the marine taxon. Skip the obviously non-marine iconic groups.
    skip_iconic = {"Insecta", "Arachnida", "Plantae", "Fungi", "Amphibia"}
    for r in results:
        if r.get("iconic_taxon_name") in skip_iconic:
            continue
        photo = r.get("default_photo") or {}
        url = photo.get("medium_url")
        if not url:
            continue  # only return taxa that actually have a usable photo
        matches.append(
            {
                "scientific_name": r.get("name"),
                "common_name": r.get("preferred_common_name"),
                "rank": r.get("rank"),
                "photo_url": url,
                "attribution": photo.get("attribution"),
                "inat_taxon_id": r.get("id"),
            }
        )
        if len(matches) >= limit:
            break
    return {
        "found": bool(matches),
        "query": species,
        "images": matches,
        "error": None if matches else f"No photos found for '{species}'.",
        "note": "Show the attribution line alongside any displayed photo.",
        "source": "iNaturalist",
    }


# --- 5. Taxonomic search (candidate identification) ------------------------------------
def _worms_brief(r: dict) -> dict:
    return {
        "aphia_id": r.get("AphiaID"),
        "scientific_name": r.get("scientificname"),
        "authority": r.get("authority"),
        "rank": r.get("rank"),
        "status": r.get("status"),
        "valid_name": r.get("valid_name"),
        "classification": {
            "phylum": r.get("phylum"),
            "class": r.get("class"),
            "order": r.get("order"),
            "family": r.get("family"),
            "genus": r.get("genus"),
        },
        "worms_url": r.get("url"),
    }


async def search_taxa(query: str, fuzzy: bool = True, limit: int = 8) -> dict:
    """Search WoRMS for marine taxa matching ``query``. Tries scientific name first
    (fuzzy by default), then falls back to common/vernacular names."""
    candidates: list[dict] = []
    seen: set[int] = set()

    # 1) Scientific-name match.
    try:
        name_url = f"{WORMS_BASE}/AphiaRecordsByName/{quote(query)}"
        data = await _get_json(name_url, {"like": str(fuzzy).lower(), "marine_only": "true"}, allow_empty=True)
        if isinstance(data, list):
            for r in data:
                aid = r.get("AphiaID")
                if aid and aid not in seen:
                    seen.add(aid)
                    candidates.append(_worms_brief(r))
    except Exception:  # noqa: BLE001 - vernacular fallback may still succeed
        pass

    # 2) Vernacular (common-name) fallback when scientific match was thin.
    if len(candidates) < limit:
        try:
            vern_url = f"{WORMS_BASE}/AphiaRecordsByVernacular/{quote(query)}"
            vdata = await _get_json(vern_url, {"like": "true"}, allow_empty=True)
            if isinstance(vdata, list):
                for r in vdata:
                    aid = r.get("AphiaID")
                    if aid and aid not in seen:
                        seen.add(aid)
                        candidates.append(_worms_brief(r))
        except Exception:  # noqa: BLE001
            pass

    candidates = candidates[:limit]
    return {
        "found": bool(candidates),
        "query": query,
        "candidates": candidates,
        "error": None if candidates else f"No marine taxa matched '{query}'.",
        "source": "WoRMS",
    }


# --- 6. Species detail (verification + conservation) -----------------------------------
def _extract_iucn(attrs: Any) -> Optional[str]:
    """Best-effort scan of WoRMS attributes for an IUCN Red List category."""
    if not isinstance(attrs, list):
        return None
    stack = list(attrs)
    while stack:
        node = stack.pop()
        if not isinstance(node, dict):
            continue
        mtype = (node.get("measurementType") or "").lower()
        mval = node.get("measurementValue")
        if "iucn" in mtype and mval:
            return str(mval)
        children = node.get("children")
        if isinstance(children, list):
            stack.extend(children)
    return None


async def species_detail(aphia_id: int) -> dict:
    """Authoritative detail for a WoRMS AphiaID: taxonomy, environment flags (used to
    judge whether a sighting is plausible), known distribution localities, and IUCN
    conservation status when available."""
    try:
        rec = await _get_json(f"{WORMS_BASE}/AphiaRecordByAphiaID/{aphia_id}", allow_empty=True)
    except Exception as exc:  # noqa: BLE001
        return {"found": False, "error": f"Species record request failed: {exc}"}
    if not isinstance(rec, dict):
        return {"found": False, "error": f"No WoRMS record for AphiaID {aphia_id}."}

    # Distribution + attributes are best-effort; absence shouldn't fail the whole call.
    dist_localities: list[str] = []
    try:
        dist = await _get_json(f"{WORMS_BASE}/AphiaDistributionsByAphiaID/{aphia_id}", allow_empty=True)
        if isinstance(dist, list):
            dist_localities = [d.get("locality") for d in dist if d.get("locality")][:25]
    except Exception:  # noqa: BLE001
        pass

    iucn = None
    try:
        attrs = await _get_json(
            f"{WORMS_BASE}/AphiaAttributesByAphiaID/{aphia_id}", {"include_inherited": "true"}, allow_empty=True
        )
        iucn = _extract_iucn(attrs)
    except Exception:  # noqa: BLE001
        pass

    return {
        "found": True,
        "aphia_id": aphia_id,
        "scientific_name": rec.get("scientificname"),
        "authority": rec.get("authority"),
        "rank": rec.get("rank"),
        "status": rec.get("status"),
        "valid_name": rec.get("valid_name"),
        "classification": {
            "kingdom": rec.get("kingdom"),
            "phylum": rec.get("phylum"),
            "class": rec.get("class"),
            "order": rec.get("order"),
            "family": rec.get("family"),
            "genus": rec.get("genus"),
        },
        "environment": {
            "is_marine": rec.get("isMarine"),
            "is_brackish": rec.get("isBrackish"),
            "is_freshwater": rec.get("isFreshwater"),
            "is_terrestrial": rec.get("isTerrestrial"),
            "is_extinct": rec.get("isExtinct"),
        },
        "distribution_localities": dist_localities,
        "iucn_status": iucn,
        "worms_url": rec.get("url"),
        "source": "WoRMS",
    }
