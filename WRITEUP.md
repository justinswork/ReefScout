# ReefScout: Project 3 write-up

- **Live app:** https://reefscout.onrender.com
- **Repo:** https://github.com/justinswork/ReefScout
- **Deeper docs:** [README.md](README.md) for architecture, setup, and examples; [BUILD_LOG.md](BUILD_LOG.md) for the process; [prompts/PROMPT_LOG.md](prompts/PROMPT_LOG.md) for prompt iteration; [eval/RESULTS.md](eval/RESULTS.md) for evaluation; [docs/SECURITY.md](docs/SECURITY.md) for the security audit.

This write-up answers the six required questions directly. The linked docs go into more depth.

---

## 1. What problem it solves, and who it's for

Snorkelers, tidepoolers, and shore divers keep running into two questions that the web answers
poorly. The first is "is this spot worth visiting, and when?" Today you have to stitch that answer
together yourself from a marine forecast site, a separate tide table, and a wildlife database, each
in its own units and format. The second is "what did I just see?" That one is even harder, because
text barely works for identifying marine life. A description like "small, mostly blue with some
green" fits hundreds of species, so you really can't name a fish by writing words about it.

ReefScout is built for the casual-to-intermediate snorkeler, tidepooler, or shore naturalist who
just wants one trustworthy companion for a coastal outing. It gives a clear go or no-go call based
on real conditions, tells you what wildlife you're likely to meet, identifies what you saw from a
photo or description, and keeps a personal logbook (a life-list plus a trip log) so you can
remember it later. It is meant to be informational, and it is not a safety authority.

## 2. System architecture (models, tools, and how they connect)

There is one model and one agent. It runs on Anthropic's Claude (`claude-sonnet-4-6`), which I
chose because it handles tool use well while costing less than Opus, and the deployed app runs on
my personal API key.

The tools live in a custom MCP server ([`app/mcp_server.py`](app/mcp_server.py), built with
FastMCP) that exposes seven tools: `geocode_place`, `get_marine_conditions`, `get_tides`,
`get_species_nearby`, `get_species_images`, `search_marine_taxa`, and `get_species_detail`. Each
one wraps a free, no-API-key live source in [`app/ocean_data.py`](app/ocean_data.py): Open-Meteo
for geocoding and marine conditions, NOAA CO-OPS for tides, iNaturalist for sightings and photos,
and WoRMS for taxonomy and conservation status.

They connect like this. The browser (a single-file UI) posts to the FastAPI `/chat` route, which
runs the agent loop in [`app/agent.py`](app/agent.py). The loop calls the Anthropic API, and
whenever the model asks to use a tool, the loop dispatches that call over MCP (stdio) to the tool
server and feeds the result back. Conversation history and the logbook are handled separately by
Firebase (Auth and Firestore) directly from the browser, so the agent backend never holds any
Firebase credentials. There's a full diagram and a component table in the
[README](README.md#architecture).

## 3. What is agentic about it

The model is in charge, not my Python. The loop in [`app/agent.py`](app/agent.py) reads the
model's `tool_use` blocks, runs those tools, hands the results back, and repeats until the model
decides it's finished. The model picks which tools to call, what order to call them in, whether to
call any at all, and when to stop. Nothing in my code uses an `if/else` to decide the tool chain.

You can see this in the real traces in the
[README](README.md#a-complete-interaction-real-output-lightly-trimmed). When a
`geocode_place("La Jolla Cove")` call came back empty, the model retried with the simpler
"La Jolla" on its own. When a question only asks about waves, it never calls the species tool (the
evaluation checks for exactly this). And when someone claimed they saw a clownfish at La Jolla, it
searched the taxonomy, checked whether the species actually occurs there, refuted the claim with
evidence, and suggested the garibaldi instead.

The simplest way to put it: if you swapped the model out for a lookup table, all of that branching,
verification, and synthesis would vanish. So it really is agentic, not a fixed pipeline.

## 4. How I evaluated it

[`eval/run_eval.py`](eval/run_eval.py) defines what "good" means as three things I can actually
test, and it runs nine structured cases against the real agent. The first is agentic correctness,
which checks the tool-call trace to confirm the right tools fire for each kind of question,
including a negative case where a conditions-only question must not call the species tool. The
second is grounded answers, where relative dates have to resolve to real calendar dates, the
verdict comes first, and measurements appear in both metric and imperial. The third is honesty at
the edges, where an out-of-range identification has to be challenged and an off-topic request has
to be declined without spending any tool calls.

The suite passes nine out of nine. An earlier run scored seven out of eight, and that documented
failure (the verdict wasn't coming first) is what drove the move to prompt v2. The run history and
the kept failure are in [`eval/RESULTS.md`](eval/RESULTS.md). On top of that there are 14 `pytest`
integration tests covering the data layer, the MCP server, and the API.

## 5. What changed from draft feedback

The full mapping is in [BUILD_LOG.md](BUILD_LOG.md#draft--final-instructor-feedback). The draft
feedback validated the MCP server, the agent loop, the prompt log, and the grounding, and it
flagged two things to finish: the build log, and a full README that includes a complete example
showing the whole tool chain.

I had actually just finished both the build log and the README when that feedback arrived, so the
useful thing it pushed me to do was add a second worked example. The README now walks through an
identification with verification as well as the planning flow, and between the two examples all
seven tools are shown end to end. Plenty of iteration happened on my own along the way too: the
system prompt went from v1 to v2 (seven out of eight to eight out of eight, after I made the
verdict come first and capped the geocode retries) and then to v3 for photo identification, and I
fixed a date-grounding bug and a reference-photo mismatch (both written up in the build log).

## 6. What breaks, and what I'd fix with more time

A few honest limitations and failure modes:

- iNaturalist has no strict marine filter, so a coastal `get_species_nearby` query can occasionally
  return a land animal like a garden snail. I tell the agent to sanity-check this, but it isn't
  perfect.
- Tides come from NOAA, which only covers US coasts. Outside the US the app says tide data isn't
  available rather than guessing, which is correct but still a coverage gap.
- In regions that aren't well studied, the species lists are thin, so quality tracks how much data
  exists for a given coast.
- Photo identification depends on both the model's vision and the candidate it reasons toward, so a
  poor photo can still throw it off. I have evaluation cases for text identification but not yet for
  image identification.
- The rate limiter is in-memory on a single Render instance, so it resets on restart. It's a
  deterrent rather than a hard boundary; the real cost ceiling is the spend limit on the API key
  (covered in the security audit).
- Prompt injection can still coax some off-topic output, though the rate limits and the key's spend
  cap keep the blast radius small.

What I'd do with more time:

- Add a proper marine filter for sightings, cross-checking the WoRMS `isMarine` flag or OBIS
  occurrence data, to clear out the terrestrial noise.
- Cache the geocode, taxonomy, and photo lookups to cut latency and go easier on the free upstream
  APIs.
- Stream responses so multi-tool turns feel faster.
- Build image-identification evaluation cases with labeled photos so I can measure vision accuracy,
  not just text accuracy.
- Support full-resolution and multiple user photos via Firebase Storage, and move to distributed
  rate limiting (Redis) if it ever ran on more than one instance.
