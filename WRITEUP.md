# ReefScout — Project 3 write-up

- **Live app:** https://reefscout.onrender.com
- **Repo:** https://github.com/justinswork/ReefScout
- **Deep docs:** [README.md](README.md) (architecture, setup, examples) · [BUILD_LOG.md](BUILD_LOG.md) (process) · [prompts/PROMPT_LOG.md](prompts/PROMPT_LOG.md) (prompt iteration) · [eval/RESULTS.md](eval/RESULTS.md) (evaluation) · [docs/SECURITY.md](docs/SECURITY.md) (security audit)

This write-up answers the six required questions directly; the linked docs go deeper.

---

## 1. What problem it solves, and who it's for

Snorkelers, tidepoolers, and shore divers face two recurring, annoying questions, and the web
answers them badly:

1. **"Is it worth going to this spot, and when?"** — the answer is scattered across a marine
   forecast site, a tide table, and a wildlife database, in different units and formats.
2. **"What did I just see?"** — and here text fails completely. *"Small, mostly blue with some
   green"* matches hundreds of species; you can't identify a fish by describing it in words.

**ReefScout** is for the **casual-to-intermediate snorkeler / tidepooler / shore naturalist** who
wants a single, trustworthy companion for a coastal outing: a go/no-go call with real conditions,
the wildlife they're likely to meet, photo-based identification of what they saw, and a personal
**logbook** (life-list + trips) to remember it. It is informational, not a safety authority.

## 2. System architecture (models, tools, how they connect)

- **Model:** a single agent — Anthropic **Claude (`claude-sonnet-4-6`)** — chosen for strong tool
  use at lower cost than Opus (it runs on a personal API key).
- **Tools:** a **custom MCP server** ([`app/mcp_server.py`](app/mcp_server.py), FastMCP) exposing
  **7 tools** — `geocode_place`, `get_marine_conditions`, `get_tides`, `get_species_nearby`,
  `get_species_images`, `search_marine_taxa`, `get_species_detail` — each backed by a **free,
  no-API-key** live source ([`app/ocean_data.py`](app/ocean_data.py)): Open-Meteo (geocoding +
  marine), NOAA CO-OPS (tides), iNaturalist (sightings + photos), WoRMS (taxonomy + conservation).
- **How they connect:** Browser (single-file UI) → FastAPI `/chat` → the **agent loop**
  ([`app/agent.py`](app/agent.py)) → Anthropic API; when the model emits `tool_use`, the loop
  dispatches over **MCP (stdio)** to the tool server and feeds the result back. Persistence
  (history + logbook) is **client-side Firebase** (Auth + Firestore), decoupled from the agent —
  the backend never holds Firebase credentials. Full diagram + component table in the
  [README](README.md#architecture).

## 3. What is agentic about it

The model — not Python — drives. The loop in [`app/agent.py`](app/agent.py) reads `tool_use`
blocks, dispatches them, feeds results back, and repeats **until the model decides to stop**. The
model chooses *which* tools to call, *in what order*, *whether to call any at all*, and *when it's
done*. No `if/else` routing decides the tool chain. Observed autonomous behavior (real traces in
the [README](README.md#a-complete-interaction-real-output-lightly-trimmed)):

- **Recovers from failure:** a failed `geocode_place("La Jolla Cove")` → retried `"La Jolla"` on its own.
- **Skips unneeded tools:** a waves-only question never calls the species tool (asserted in the eval).
- **Multi-step verification:** a claimed *clownfish at La Jolla* → it searched taxonomy, checked
  local occurrence, **refuted the ID with evidence**, and proposed the garibaldi instead.

**Litmus test:** replace the LLM with a lookup table and the branching, verification, and synthesis
all disappear — so it's genuinely agentic, not a pipeline.

## 4. How I evaluated it

[`eval/run_eval.py`](eval/run_eval.py) defines "good" as three *executable* dimensions and tests
9 structured cases against the real agent:

- **Agentic correctness** — asserts on the **tool-call trace** that the right tools fire per
  question type, *including a negative case* (a conditions-only question must NOT call the species tool).
- **Grounded answers** — relative dates resolve to real calendar dates, verdict-first format, dual units.
- **Honesty at the edges** — an out-of-range ID is challenged; off-topic is declined with zero tool calls.

**Result: 9/9.** An earlier run scored **7/8**; the documented failure (verdict not first) drove
prompt v2. Run history and the kept failure are in [`eval/RESULTS.md`](eval/RESULTS.md). There are
also 14 `pytest` integration tests over the data layer, MCP server, and API.

## 5. What changed from draft feedback

Instructor draft feedback (full mapping in [BUILD_LOG.md](BUILD_LOG.md#draft--final-instructor-feedback)):
the MCP server, agent loop, prompt log, and grounding were validated; the action items were
**finish the build log** and **write the full README, with a complete example showing the full
tool chain.**

- Both the build log and the full README had just been completed; the feedback drove one concrete
  improvement — I added a **second worked example** (an identification with verification) so the
  README now demonstrates **all 7 tools** end-to-end, not just the planning flow.
- Self-driven iteration also happened throughout: prompt **v1 → v2** (7/8 → 8/8, verdict-first +
  bounded geocode retries) and **v3** (photo ID), plus fixes for a date-grounding bug and a
  reference-photo mismatch (see BUILD_LOG).

## 6. What breaks, and what I'd fix with more time

**Known limitations / failure modes:**

- **iNaturalist has no strict marine filter**, so coastal `get_species_nearby` results can include
  the occasional terrestrial taxon (e.g. a land snail). The agent is told to sanity-check, but it's
  imperfect.
- **Tides are US-only** (NOAA). For non-US coasts the app says tide data is unavailable rather than
  guessing — correct, but a coverage gap.
- **Sparse-data regions** yield thin species lists; quality tracks how well-studied a coast is.
- **Photo ID accuracy** depends on the model's vision + the candidate it reasons to; a poor photo
  can still mislead it. There are eval cases for text ID but not yet for image ID.
- **The rate limiter is in-memory** (single Render instance) and resets on restart — a deterrent,
  not a hard boundary. The real cost ceiling is the API-key spend limit (see security audit).
- **Prompt injection** can coax off-topic output (bounded by rate limits + the key's spend cap).

**What I'd do with more time:**

- A real marine filter for sightings (cross-check WoRMS `isMarine` / OBIS occurrence) to remove
  terrestrial noise.
- **Caching** of geocode/taxonomy/photo lookups to cut latency and be kinder to the free upstream APIs.
- **Streaming** responses for faster perceived speed on multi-tool turns.
- Image-ID **eval cases** with labeled photos to measure vision accuracy, not just text ID.
- Full-resolution / multiple user photos via Firebase Storage; distributed rate limiting (Redis)
  if it ever ran multi-instance.
