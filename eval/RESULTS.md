# Eval Results

Latest full run: **2026-06-11** — 8/8 passed. 
Raw transcripts (replies + full traces) in `eval/results/` (local, gitignored). 
Case definitions and the check engine live in `eval/run_eval.py`.

| Case | Why it matters | Result | Latency | Tools called |
|---|---|---|---|---|
| `planning_basic` | Core planning flow: right tool chain, verdict-first format, both unit systems. | ✅ pass | 25.1s | geocode_place, geocode_place, get_marine_conditions, get_tides, get_species_nearby |
| `planning_with_species` | Asking what you'll see must trigger the species tool. | ✅ pass | 30.9s | geocode_place, get_marine_conditions, get_marine_conditions, get_tides, get_tides, get_species_nearby |
| `tool_economy` | A conditions-only question should NOT trigger the species tool (decision in the model). | ✅ pass | 10.0s | geocode_place, get_marine_conditions |
| `date_grounding` | Regression test for the Phase-3 bug: 'tomorrow' must resolve via the injected date. | ✅ pass | 10.1s | geocode_place, get_marine_conditions |
| `id_plausible` | ID flow: reason → taxonomy search → location verification for a species that IS local. | ✅ pass | 17.3s | search_marine_taxa, geocode_place, get_species_detail, get_species_nearby |
| `id_out_of_range` | The distinctive behavior: a clownfish 'sighting' in California must be verified and challenged, not confirmed. | ✅ pass | 25.1s | search_marine_taxa, geocode_place, search_marine_taxa, get_species_nearby, get_species_detail |
| `off_topic` | Scope guard: non-marine request → decline in one sentence, zero tool spend. | ✅ pass | 2.2s | — |
| `sparse_data_honesty` | Remote, data-poor location: must be honest about tide-station distance / data gaps, not fake precision. | ✅ pass | 16.4s | geocode_place, get_marine_conditions, get_tides |

## Run history

| Run | Prompt | Score | Notes |
|---|---|---|---|
| 2026-06-11 #1 | SYSTEM_PROMPT_V1 | 7/8 | `planning_basic` failed: verdict present but a preamble line came first ("Here's your full rundown for…"). Traces also showed 3 geocoding attempts per failed place name (one predictably-useless comma-qualified retry). |
| 2026-06-11 #2 | SYSTEM_PROMPT_V2 | 8/8 | V2 made the verdict-first rule absolute ("THE VERY FIRST LINE") and bounded geocode retries to 2 attempts. Both verified in this run's traces: verdict leads, geocoding stopped at 2 attempts. Full reasoning in `prompts/PROMPT_LOG.md`. |

Notable agentic behaviors observed across runs (visible in traces):
- "this weekend" → the model called conditions **and** tides twice — once per weekend day — without being told to.
- Claimed clownfish sighting at La Jolla → model searched taxonomy, checked local observations, **challenged the ID** and counter-proposed the garibaldi.
- Sparse-data Madagascar query (run #1) → model widened its species search radius (25→50 km) unprompted after a thin first result.

