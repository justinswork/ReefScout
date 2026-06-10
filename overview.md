# ReefScout — Overview

**ReefScout is a location-aware marine field companion.** It helps a snorkeler, tidepooler, or shore diver answer two questions about a real place on the coast:

1. **Before the trip — "Should I go, and what will I see?"**
   *e.g. "Is Saturday morning good for snorkeling at La Jolla Cove, and what might I see?"*
   ReefScout pulls live ocean conditions (waves, swell, sea-surface temperature), tide timing, and recent real-world marine-life sightings near that spot, then gives a grounded go / caution / no-go call plus a list of species you're realistically likely to encounter.

2. **After the trip — "What did I just see?"**
   *e.g. "I saw a small bright-orange fish with white vertical stripes on the reef there."*
   ReefScout searches marine taxonomy for candidate species, then **verifies each candidate against whether that species actually occurs at that location**, rules out the implausible ones, and reports the best match with its conservation status.

The unifying thread is **a place and a marine outing**. Both modes draw on the same set of tools; the species-occurrence data that powers "what will I see" is the same data that powers "is this ID plausible here." It is one coherent companion, not two apps bolted together.

---

## Why this is genuinely *agentic*

The model — not our Python — decides what to do. Given a user message, the model chooses **which** tools to call, **in what order**, and **when to stop**, based on the results it gets back.

- A planning question makes it chain `geocode_place → get_marine_conditions + get_tides + get_species_nearby → synthesize`.
- An ID question makes it chain `search_marine_taxa → (for each candidate) get_species_distribution / get_species_nearby → get_species_detail → answer with confidence`.
- The model performs **multi-step verification**: when a sighting looks out of range, it independently checks the species' known distribution before committing to an answer, and hedges when the data is thin.

**The litmus test (from the rubric):** if you removed the LLM and replaced it with a lookup table or if-statements, would the system behave the same way? No. The branching, the decision to verify, the choice of which species to rule out, and the synthesis all live in the model's responses, not in our control flow. Our code provides tools and an execution loop; the model drives.

---

## Architecture (at a glance)

```
Browser (chat UI)
      │  HTTP
      ▼
FastAPI backend  ──────────────►  Anthropic API (Claude)
   │  agent loop                    ▲   tool_use blocks
   │  (reads tool_use, dispatches,  │   tool_result blocks
   │   feeds results back, loops)   │
   ▼                                │
MCP server (FastMCP) ──────────────┘
   exposes 6 tools, each backed by a live marine API
      │
      ▼
Live data sources (free, no API key):
   • Open-Meteo Geocoding   — place name → coordinates
   • Open-Meteo Marine API  — wave height, swell period, sea-surface temp
   • NOAA CO-OPS            — tide predictions at nearest station
   • iNaturalist            — real recent marine-life observations near a point
   • WoRMS / GBIF           — marine taxonomy, fuzzy species search, distribution
   • WoRMS / IUCN           — species detail + conservation status
```

### MCP tools

| Tool | Backing source | What it does |
|---|---|---|
| `geocode_place` | Open-Meteo Geocoding | place name → latitude/longitude + nearest coast |
| `get_marine_conditions` | Open-Meteo Marine | wave height, swell period/direction, SST for a date |
| `get_tides` | NOAA CO-OPS | tide predictions (highs/lows) at the nearest station |
| `get_species_nearby` | iNaturalist | real recent marine observations near coordinates |
| `search_marine_taxa` | WoRMS / GBIF | fuzzy name/common-name search → candidate species |
| `get_species_detail` | WoRMS / IUCN | taxonomy, distribution, conservation status |

All sources are **free and require no API key**, which is deliberate: the deployed app must not crash or hang in front of the grader because of an expired key, a billing wall, or a rate-limited secret.

---

## Grounding

The model is given information it could not have known from pretraining:
- **Live conditions** (today's waves/tides/temperature) — inherently real-time.
- **Real recent sightings** near a coordinate — current crowd-sourced observation data.
- **Authoritative taxonomy and distribution** — the World Register of Marine Species, used to validate IDs rather than letting the model guess.

This is structured-input grounding (live APIs + authoritative databases) rather than a static RAG corpus.

---

## What ReefScout does *not* do (scope honesty)

- It is **not a safety authority.** Conditions guidance is informational; it does not replace lifeguards, local advisories, or a dive operator's judgment.
- It does **not identify from photos in v1.** ID works from a text description. (Image input is documented as future work.)
- It does **not discover new species or make novel scientific claims.** It reports and cross-checks existing open data.
- Coverage is best where the underlying databases are rich (well-studied coasts). For remote regions, it will say so rather than fabricate.

---

## Tech stack

- **Backend:** Python + FastAPI
- **Agent:** Anthropic Claude via the official SDK, with a tool-call loop
- **Tools:** a FastMCP server (real MCP), consumed by the backend as an MCP client
- **Frontend:** a single lightweight chat page served by FastAPI
- **Deployment:** Render free web-service tier (public URL; sleeps when idle and wakes on load, which the rubric explicitly allows)
