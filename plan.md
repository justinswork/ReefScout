# Implementation Plan

A phased plan to build ReefScout. Each phase ends in something runnable or verifiable, so
progress is visible in the git history (rubric #8) and we can course-correct early.

Legend: ☐ todo · ◐ in progress · ☑ done

---

## Phase 0 — Project setup
- ☐ `git init`, create public GitHub repo, add `debruinz` as collaborator if private.
- ☐ `.gitignore` (`.env`, `__pycache__`, `venv/`, runtime artifacts).
- ☐ `requirements.txt` (fastapi, uvicorn, anthropic, mcp, httpx, python-dotenv, pytest).
- ☐ `.env.example` documenting `ANTHROPIC_API_KEY` (and any optional vars).
- ☐ Confirm Python toolchain locally; create a virtual environment.
- ☐ First commit: scaffold + planning docs.

## Phase 1 — Live data layer (`ocean_data.py`)
Plain async functions that hit each live API and return normalized Python dicts. No LLM here.
- ☐ `geocode(place)` → Open-Meteo Geocoding.
- ☐ `marine_conditions(lat, lon, date)` → Open-Meteo Marine (wave height, swell period, SST).
- ☐ `tides(lat, lon, date)` → resolve nearest NOAA CO-OPS station, fetch hi/lo predictions.
- ☐ `species_nearby(lat, lon, radius_km)` → iNaturalist marine observations.
- ☐ `search_taxa(query)` → WoRMS/GBIF fuzzy match → candidate species.
- ☐ `species_detail(taxon_id)` → WoRMS attributes + conservation status.
- ☐ Robustness: timeouts, graceful errors, and normalized "no data" responses so the model
  can reason about gaps instead of crashing. **Verify each endpoint with a real call.**

## Phase 2 — MCP server (`mcp_server.py`)
- ☐ FastMCP server exposing the 6 tools, each wrapping a Phase-1 function.
- ☐ Each tool gets a precise **name, description, and input schema** (rubric #5). Descriptions
  written for the model: when to use the tool, what it returns, units.
- ☐ Manual check: run the server, list tools, call one by hand.

## Phase 3 — Agent loop + backend (`agent.py`, `main.py`)
- ☐ Read the `claude-api` reference before writing any Anthropic code (model IDs, tool-use loop).
- ☐ MCP client connects to the server, lists tools, converts them to the Anthropic `tools` schema.
- ☐ Tool-call loop: send messages → if `stop_reason == tool_use`, dispatch each `tool_use` to the
  MCP server, append `tool_result`, loop; else return final text (rubric #6, #7).
- ☐ Model: `claude-sonnet-4-6` (strong tool use, lower cost on the personal key).
- ☐ FastAPI routes: `POST /chat` (message in, agent reply + optional trace out), `GET /` (UI),
  `GET /health`.
- ☐ Return a **tool-call trace** alongside the answer so the UI and eval can show what the model did.

## Phase 4 — Prompts (`prompts.py` + `prompts/PROMPT_LOG.md`)
- ☐ System prompt v1: role, scope, tool-use guidance, safety disclaimer, output format.
- ☐ Test v1, find weaknesses (over-calling tools? skipping verification? unsafe overconfidence?).
- ☐ System prompt v2: revised with documented rationale (rubric #2, #3).
- ☐ Keep both versions + a written diff/why in `PROMPT_LOG.md`.

## Phase 5 — Frontend (`static/index.html`)
- ☐ Minimal chat UI: message input, conversation view, and a collapsible "what the agent did"
  trace panel (shows tool calls → makes the agentic behavior visible to the grader).
- ☐ Loading/awake state so a cold Render start is obviously "waking up," not "broken."

## Phase 6 — Evaluation (`eval/`)
- ☐ Define "good": for planning answers and for ID answers, with explicit pass criteria.
- ☐ Structured test cases:
  - Planning: known spots (e.g. La Jolla) → expect tide/condition tool calls + a clear verdict.
  - ID: a described species with a known answer + a deliberately out-of-range description that
    should trigger verification and a hedge.
  - Tool-selection: assert the model calls the *right* tools for each query type.
- ☐ Runner that executes cases, records tool traces + outputs, and reports pass/fail + latency.
- ☐ **Include documented failures** — more credible than all-green (rubric #13).

## Phase 7 — Deployment (Render)
- ☐ `render.yaml` (or dashboard config), start command `uvicorn`, `ANTHROPIC_API_KEY` env var.
- ☐ Deploy, hit the public URL, run a real interaction end-to-end (rubric #1).
- ☐ Confirm cold-start wake-up works and the UI signals it.

## Phase 8 — Documentation & build log
- ☐ `README.md`: architecture diagram, component descriptions, setup steps, a full example
  interaction trace, and an honest "what it does / does not do" section (rubric #14, #11).
- ☐ `BUILD_LOG.md`: experiments, dead ends, decisions, and the prompt-iteration story (#9, #2).
- ☐ Changelog section for **draft → final** so instructor feedback is visibly addressed (#12).

## Phase 9 — Iteration pass
- ☐ Run the eval, fix the worst failures, re-run, record the before/after.
- ☐ Submit draft → capture instructor feedback → address it → note each change.

---

## Key design decisions (and why)
- **Real MCP server, not just inline tool dicts** — maximizes the MCP rubric items (#5, #6) and
  cleanly separates "tools/data" from "agent/reasoning."
- **Free, no-key APIs only** — the deployed app cannot fail on a missing/expired secret (#1).
- **Tool trace surfaced in UI + eval** — makes the otherwise-invisible agentic decisions legible
  to the grader (#6, #7, #13).
- **Occurrence-based ID verification** — the distinctive idea: don't just guess a species, check
  whether it can actually be there (#10, originality).
- **Scope honesty** — explicit non-goals and a safety disclaimer; the model is told to hedge when
  data is thin rather than fabricate (#11).

## Open questions / risks
- iNaturalist / WoRMS rate limits under grading load → add light caching + polite timeouts.
- NOAA station resolution for spots far from a station → fall back gracefully and say so.
- Render cold-start latency → UI "waking up" state; keep the agent loop lean.
- Personal API-key cost on the deployed app → use Sonnet, cap loop iterations, keep prompts tight.
