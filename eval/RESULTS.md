# Eval Results

Latest full run: **2026-06-11** — 9/9 passed. 
Raw transcripts (replies + full traces) in `eval/results/` (local, gitignored). 
Case definitions and the check engine live in `eval/run_eval.py`.

| Case | Why it matters | Result | Latency | Tools called |
|---|---|---|---|---|
| `planning_basic` | Core planning flow: right tool chain, verdict-first format, both unit systems. | ✅ pass | 29.4s | geocode_place, geocode_place, get_marine_conditions, get_tides, get_species_nearby |
| `planning_with_species` | Asking what you'll see must trigger the species tool. | ✅ pass | 35.3s | geocode_place, get_marine_conditions, get_marine_conditions, get_tides, get_tides, get_species_nearby, get_species_images, get_species_images, get_species_images, get_species_images, get_species_images |
| `tool_economy` | A conditions-only question should NOT trigger the species tool (decision in the model). | ✅ pass | 11.8s | geocode_place, get_marine_conditions |
| `date_grounding` | Regression test for the Phase-3 bug: 'tomorrow' must resolve via the injected date. | ✅ pass | 11.0s | geocode_place, get_marine_conditions |
| `id_plausible` | ID flow: reason → taxonomy search → location verification for a species that IS local. | ✅ pass | 22.1s | geocode_place, search_marine_taxa, get_species_nearby, get_species_detail, get_species_images |
| `id_out_of_range` | The distinctive behavior: a clownfish 'sighting' in California must be verified and challenged, not confirmed. | ✅ pass | 24.9s | geocode_place, search_marine_taxa, get_species_nearby, get_species_detail, get_species_images |
| `id_shows_photo` | Identification with a photo request must fetch a reference image and embed it with attribution. | ✅ pass | 20.1s | geocode_place, search_marine_taxa, get_species_nearby, get_species_images, get_species_detail |
| `off_topic` | Scope guard: non-marine request → decline in one sentence, zero tool spend. | ✅ pass | 2.4s | — |
| `sparse_data_honesty` | Remote, data-poor location: must be honest about tide-station distance / data gaps, not fake precision. | ✅ pass | 25.4s | geocode_place, get_marine_conditions, get_tides, get_species_nearby |

## Run history

| Run | Prompt | Score | Notes |
|---|---|---|---|
| 2026-06-11 #1 | V1 | 7/8 | `planning_basic` failed: verdict present but a preamble line came first. Traces showed 3 geocoding attempts per failed place name (one useless comma-qualified retry). |
| 2026-06-11 #2 | V2 | 8/8 | V2 made the verdict-first rule absolute and bounded geocode retries to 2. Both verified in traces. |
| 2026-06-11 #3 | V3 | 9/9 | Added image identification (`get_species_images` tool, photo upload, V3 photo workflow) + the `id_shows_photo` case. No regression on the prior 8. |

Reasoning for each prompt version is in `prompts/PROMPT_LOG.md`.

## Notable agentic behaviors observed (visible in traces)
- "this weekend" → the model called conditions **and** tides twice, once per weekend day, unprompted.
- Claimed clownfish sighting at La Jolla → searched taxonomy, checked local observations, **challenged the ID** and counter-proposed the garibaldi.
- Sparse-data Madagascar query → widened its species search radius (25→50 km) unprompted after a thin first result.
- "What will I see?" → fetched reference photos for several highlight species so the user knows what to look for, not just names.

