# Build Log

How ReefScout was actually built — the concept pivots, the architectural decisions and why,
the things that didn't work, and the bugs found along the way. Prompt-specific iteration lives in
[prompts/PROMPT_LOG.md](prompts/PROMPT_LOG.md); this is the wider story. The git history is the
fine-grained record — each phase below maps to one or more commits.

---

## Finding the concept

I knew I wanted something agentic with a real MCP tool and genuine grounding, and I'm drawn to the
ocean. The idea took a few turns before it landed:

1. **A marine "field companion"** (plan a snorkel trip + identify what you saw). Liked it, but
   wanted something with more mission.
2. **An "ocean discovery" agent** — surface under-explored areas and anomalies from open
   biodiversity data. Compelling, but honestly hard to make rigorous: an LLM can't *discover* a
   species, only mine existing data, and dressing that up as "discovery" felt overstated.
3. **An ocean-trash / cleanup assistant.** Strong real-world impact, but the freshest, most
   reliable data sources needed keys or were patchy — risky for a deployment that must not break.
4. **Back to the field companion (ReefScout).** It had the best combination of: clean agentic
   tool-chaining, free no-key grounding data, a defensible scope, and room to grow (which it did,
   into photo ID and a logbook).

**Lesson:** the deciding factor wasn't the flashiest idea — it was which concept had *reliable,
free, key-less data*, because rubric item #1 (a deployed app that doesn't break) depends on it.

---

## Decisions that shaped the build

### Free, no-API-key data only
Every live source (Open-Meteo, NOAA CO-OPS, iNaturalist, WoRMS) is free and needs no key. This was
deliberate: a deployed app that depends on a billable or expiring secret is one quota limit away
from failing in front of a grader. Before writing the data layer I hit all of them with `curl` to
confirm shapes and that they were truly key-less — that early verification caught the NOAA
"nearest-station" requirement and iNaturalist's lack of a strict marine filter.

### A real MCP server, not inline tool dicts
The tools could have been plain dicts passed to the Anthropic API. Instead I built an actual
FastMCP server ([`app/mcp_server.py`](app/mcp_server.py)) that the backend connects to as an MCP
*client* over stdio. It's more moving parts, but it (a) cleanly separates "tools/data" from
"agent/reasoning," and (b) is the honest interpretation of the MCP requirement.

### A manual tool-call loop, not the SDK's auto-runner
The Anthropic SDK has a tool-runner that hides the loop. I wrote the loop by hand
([`app/agent.py`](app/agent.py)) because the loop *is* the evidence of agentic behavior, and I
wanted to capture a **tool-call trace** for every turn — which became both the UI's "what the agent
did" panel and the thing the eval asserts against.

### Decoupled persistence
When conversation history and the logbook came along, the cleanest design kept the agent backend
ignorant of Firebase: the browser talks to Firestore directly under per-user security rules. The
FastAPI service never holds Firebase credentials, and the agent never depends on the database.

---

## What didn't work (and the fixes)

- **"Tomorrow" resolved to the wrong year.** The first live test of the agent produced a date in
  the wrong year because the model inferred "tomorrow" from training data. Fix: inject today's date
  as a system block placed *after* the prompt-cache breakpoint, so the fix doesn't invalidate the
  cache. (Caught the value of testing against the live model early.)

- **Prompt v1 put the verdict second.** The first eval run scored 7/8 — the answer led with a
  preamble ("Here's your full rundown for…") before the verdict. v1's "lead with the answer" was
  too soft; v2 made it absolute ("THE VERY FIRST LINE… no greeting"). Traces also showed a wasteful
  third geocoding retry, so v2 bounded retries to two attempts. → 8/8. (Full diff in PROMPT_LOG.)

- **"Moon jelly" returned a photo of a butterfly.** WoRMS resolves "moon jelly" to the bare genus
  *Aurelia*, and an iNaturalist photo search for "Aurelia" fuzzy-matched an insect ahead of the
  jelly. Two fixes: the photo lookup now skips non-marine iconic taxa (Insecta/Arachnida/Plantae/
  Fungi), and for genus-only matches the resolve endpoint queries by the user's common name
  instead of the ambiguous genus.

- **Mini-markdown choked on nested emphasis and tables.** The hand-rolled markdown renderer broke
  on `**Garibaldi (*Hypsypops*)**` and didn't render tables at all (planning answers are full of
  them). Both fixed in the renderer; tables now render as glass grids.

- **A CSS stacking-context trap.** The account dropdown rendered *behind* the hero panel because the
  header's `backdrop-filter` creates a stacking context. Fix: lift the header above the scrolling
  content. (Also: `[hidden]` on icon buttons was being overridden by an author `display:` rule.)

- **The committed Firebase key tripped GitHub's scanner.** The Firebase web key is public by
  design, but rather than keep it in source I moved the config to a runtime `/firebase-config.js`
  route fed by env vars, removed the committed file, and documented restricting the key in GCP.

---

## Features added along the way (user-driven)

- **Photo identification** (prompt v3): upload a photo → the model identifies from the image, and
  reference photos of candidates are shown for visual comparison via the `get_species_images` tool.
- **Conversation history + naturalist logbook**: Firebase Auth (Google) + Firestore. The logbook is
  a life-list grouped by taxon, with trips, conservation status, and stats.
- **Chat → logbook shortcut**: an "➕ Add \<species\> to logbook" button on any identification,
  pre-filled with the species (parsed from the reply) and the place (pulled from the geocode in the
  tool trace).
- **Auto-enriched sightings**: the logbook form asks only for name/place/date/notes; a keyless
  `/species/resolve` endpoint fills in scientific name, taxon group, conservation status, and a
  reference photo from WoRMS + iNaturalist.

### Deliberately deferred
- **Full-resolution / multiple user photos** (would need Firebase Storage, which requires a billing
  upgrade). v1 stores one downscaled photo per sighting directly in Firestore instead.
- **Cross-device history without login** isn't possible without identity; signed-out use is
  ephemeral by design.

---

## How to verify the claims here
- Live app: <https://reefscout.onrender.com> (`/health` reports whether the agent is live).
- `pytest` — 14 integration tests (data layer, MCP server, API).
- `python -m eval.run_eval` — the 9-case evaluation; results in [eval/RESULTS.md](eval/RESULTS.md).
- `git log` — the phase-by-phase commit history.
