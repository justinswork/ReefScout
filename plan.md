# Implementation Plan

A phased plan to build ReefScout. Each phase ends in something runnable or verifiable, so
progress is visible in the git history (rubric #8) and we can course-correct early.

Legend: ☐ todo · ◐ in progress · ☑ done

> **Added mid-build (user request):** image identification — users upload photos (vision
> input) and the agent returns reference photos of candidate species to compare against.
> Shipped as a 7th MCP tool (`get_species_images`), multimodal `/chat`, UI photo upload, and
> system prompt V3. Folded into Phases 1–6 below rather than a new phase.
>
> **Added mid-build (user request):** conversation history — Firestore + Google sign-in
> (Firebase Auth), client-side. Backend stays on Render and never touches Firebase. Chat works
> signed-out (ephemeral); persistence + a history drawer appear when signed in. Setup in
> `docs/FIREBASE_SETUP.md`; rules in `firestore.rules`. Also fixed two UI bugs found while
> building it: markdown tables now render (planning answers use them heavily), and the `[hidden]`
> attribute on icon buttons was being overridden by author CSS.
>
> **Added mid-build (user request):** naturalist **logbook** — a life-list of wildlife sightings
> (grouped by taxon: fish, mollusks, turtles, crustaceans…) + logged trips, per signed-in user.
> New Firestore collections `users/{uid}/sightings` + `users/{uid}/trips` (rules updated — must be
> re-published). Full-view UI with stats (species/sightings/trips/places + conservation-concern
> count), add/edit/delete modals, and an **"➕ Add to logbook"** button on agent ID replies that
> pre-fills the species (common + scientific name, taxon group inferred) from the reply. Signed-out
> users don't see it.
>
> **Added mid-build (user request):** sighting **photos** — every sighting has one. Reference photo
> from iNaturalist by default (via `/species/resolve`, with attribution); the user can upload their
> own, downscaled client-side and stored as a compact JPEG inside the sighting's Firestore doc (one
> per doc, under 1 MB → no Firebase Storage / billing upgrade needed). Photo lookup skips non-marine
> matches and uses the common name for genus-only results (fixed a moon-jelly→butterfly mismatch).

---

## Phase 0 — Project setup ☑
- ☑ `git init`; public GitHub repo at github.com/justinswork/ReefScout (public → no collaborator needed).
- ☑ `.gitignore` (`.env`, `__pycache__`, `venv/`, runtime artifacts).
- ☑ `requirements.txt` (fastapi, uvicorn, anthropic, mcp, httpx, python-dotenv, pytest).
- ☑ `.env.example` documenting `ANTHROPIC_API_KEY` (and any optional vars).
- ☑ Confirm Python toolchain locally (git 2.48, Python 3.10.11). Target **Python 3.10** compatibility.
- ☐ Create a virtual environment + install deps (start of Phase 1).
- ☑ Initial commits: planning docs, then scaffold (two commits, pushed to `main`).

## Phase 1 — Live data layer (`app/ocean_data.py`) ☑
Plain async functions that hit each live API and return normalized Python dicts. No LLM here.
- ☑ `geocode(place)` → Open-Meteo Geocoding.
- ☑ `marine_conditions(lat, lon, date)` → Open-Meteo Marine (daily wave/swell maxima + avg SST).
- ☑ `tides(lat, lon, date)` → nearest NOAA CO-OPS station (cached station list + haversine) → hi/lo.
- ☑ `species_nearby(lat, lon, radius_km)` → iNaturalist species_counts (ranked by observations).
- ☑ `search_taxa(query)` → WoRMS by scientific name (fuzzy) + vernacular fallback.
      (GBIF dropped for v1 — WoRMS scientific+vernacular search covered the need cleanly.)
- ☑ `species_detail(aphia_id)` → WoRMS record + environment flags + distribution + IUCN status.
- ☑ Robustness: 15s timeouts, polite User-Agent, all upstream failures normalized to
  `{"found": False, "error": ...}`. Verified with 8 live integration tests (`pytest -m live`, all green).

## Phase 2 — MCP server (`app/mcp_server.py`) ☑
- ☑ FastMCP server (`reefscout-ocean`) exposing the 6 tools, each wrapping a Phase-1 function.
- ☑ Each tool has a precise **name, description, and input schema** (rubric #5). Descriptions
  written for the model: when to use the tool, what it returns, units, caveats, and guidance
  (e.g. search_marine_taxa explicitly says "reason to candidate names first, it does NOT
  understand free-form descriptions" — tool descriptions are part of the prompt design).
- ☑ Verified over real stdio JSON-RPC in `tests/test_mcp_server.py`: list_tools shows all 6
  with schemas; call_tool("geocode_place") executes end-to-end. Both tests green.

## Phase 3 — Agent loop + backend (`app/agent.py`, `app/main.py`) ☑
- ☑ Read the `claude-api` reference before writing Anthropic code.
- ☑ `ReefScoutAgent`: persistent MCP client (stdio subprocess spawned once at FastAPI startup
  via lifespan), lists tools, converts MCP schemas → Anthropic `tools` shape.
- ☑ Manual tool-call loop (deliberately not the SDK auto-runner — the loop is the rubric
  evidence): `stop_reason == "tool_use"` → dispatch each block over MCP → append tool_result →
  loop; else return text. 12-iteration safety cap. (#6, #7)
- ☑ Model: `claude-sonnet-4-6` (REEFSCOUT_MODEL overridable). Prompt caching: breakpoint on
  the stable system block (caches tools+system); volatile date block placed after it.
- ☑ `/chat` runs the real agent; demo mode only as explicit no-API-key fallback.
- ☑ Tool-call trace ({tool, args, summary, ms}) returned with every reply → UI + eval.
- ☑ Smoke-tested live: planning question chained geocode→conditions→tides(→species when asked).
  **Findings:** (a) model retried failed geocode 'La Jolla Cove'→'La Jolla' unprompted —
  adaptive behavior; (b) caught grounding bug: model resolved "tomorrow" from training data
  (wrong year) — fixed by injecting today's date as a post-breakpoint system block;
  (c) model omits species lookup when the question doesn't ask about wildlife.

## Phase 4 — Prompts (`app/prompts.py` + `prompts/PROMPT_LOG.md`) ☑
- ☑ System prompt V1: role, scope, tool-use guidance, safety disclaimer, output format.
- ☑ Tested V1 via the eval (7/8): verdict-not-first failure + geocode-retry thrash found.
- ☑ System prompt V2: absolute first-line verdict rule + bounded geocode retry policy.
  Re-run: 8/8. Both versions kept in code; full diff + lessons in `PROMPT_LOG.md` (#2, #3).

## Phase 5 — Frontend (`static/index.html`) ☑ *(pulled ahead of Phases 3–4)*
Scope upgraded from "minimal chat UI" to a polished ocean-themed **Liquid Glass** design:
deep-ocean gradient, animated god rays + caustic shimmer + rising bubbles (with
prefers-reduced-motion fallback), translucent blurred-glass surfaces with specular highlights.
- ☑ Chat UI: hero with mode cards + suggestion chips, user/agent glass bubbles, safe
  mini-markdown renderer, autosizing composer.
- ☑ Collapsible "what the agent did" trace panel per agent message (tool icon, name, summary,
  latency) — makes agentic behavior visible to the grader (#6, #7).
- ☑ `app/main.py` FastAPI serves the UI + `/chat`; **demo-mode stub** returns the final response
  contract ({reply, trace, demo:true}) with a visible "demo mode" badge until Phase 3 lands.
- ☑ Cold-start handling: fetch failure renders a friendly "server waking up" message.
- ☑ Verified in live browser preview: full send→reply flow, trace expansion, badge toggle.

## Phase 6 — Evaluation (`eval/`) ☑
- ☑ "Good" defined as 3 executable dimensions: agentic correctness (right tools per question
  type, asserted on traces), grounded answers (dates/format/units), honesty at the edges
  (out-of-range ID challenged, off-topic declined with zero tool spend).
- ☑ 8 structured cases in `eval/run_eval.py` incl. planning, species, tool-economy (negative
  assertion), date-grounding regression, plausible ID, out-of-range ID, off-topic, sparse-data.
- ☑ Declarative check engine (tools_include/exclude, tool_arg_matches, reply regex, any_of);
  runner records pass/fail + latency + full traces → `eval/RESULTS.md` (committed) +
  raw JSON (local).
- ☑ Documented failure preserved: V1 run 7/8 (verdict-not-first) → drove prompt V2 → 8/8.
  Run history table in RESULTS.md keeps the failure visible (#13, #12, #2).

## Phase 7 — Deployment (Render) ◐
- ☑ `render.yaml` blueprint: free web service, `uvicorn app.main:app`, health check `/health`,
  `PYTHON_VERSION` pinned, secrets (`ANTHROPIC_API_KEY`, `FIREBASE_*`) as dashboard env vars.
- ☑ Pinned `requirements.txt` to tested versions for reproducible builds.
- ☑ `docs/DEPLOY.md` step-by-step (blueprint flow + env vars + Firebase authorized domain).
- ☐ **User action:** create the Render service from the blueprint, set the secret env vars.
- ☐ Add the Render domain to Firebase Authorized domains (+ key HTTP-referrer allowlist).
- ☐ Hit the public URL, run a real interaction end-to-end, confirm cold-start wake-up (rubric #1).

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
