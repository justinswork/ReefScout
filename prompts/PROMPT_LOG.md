# Prompt Log

Running record of system-prompt versions: what each version says, what we observed when
testing it, and why the next version changed. The live prompt is `app/prompts.py::SYSTEM_PROMPT`;
all versions are kept in that file as `SYSTEM_PROMPT_V1`, `V2`, ...

---

## V1 — initial prompt (2026-06-11)

**Design intent**, section by section:

| Section | Why it's there |
|---|---|
| Role + two-task scope | Pin the agent to planning + ID; gives a basis for declining off-topic requests. |
| Tool guidance | The critical agentic part: tells the model to geocode first, and for IDs to *reason to candidate names first, then verify with tools* — because WoRMS search can't parse free-form descriptions (learned in Phase 1 testing). Verification-before-assertion is the distinctive behavior we want graded. |
| Grounding rules | Every number must come from a tool result; hedge when data is thin. Anti-hallucination backbone. |
| Safety | Informational-only stance, defer to lifeguards. One note, not repeated boilerplate. |
| Style | Bolded verdict first (planning) / confidence-cued match (ID); metric + imperial; tight markdown. Makes outputs predictable and gradeable in eval. |

**Hypotheses to test against V1** (will drive V2):
1. Does it actually verify ID candidates against location, or skip straight to an answer?
2. Does it over-call tools on simple questions (e.g. geocoding when coordinates are already known from earlier in the conversation)?
3. Does it hedge appropriately when iNaturalist data is sparse, or fake confidence?
4. Does the verdict-first format hold up across phrasings?

**First live observations (2026-06-11, smoke tests):**
- ✅ Hypothesis 4 partially confirmed good: verdict-first format held (**Marginal — ...**), both
  unit systems present, tight sections.
- ✅ Unprompted adaptive behavior: when `geocode_place("La Jolla Cove")` returned no match, the
  model retried with the simpler "La Jolla" — exactly the recovery the tool description suggests.
- ✅ Tool selection follows the question: "what might I see?" → species lookup included; same
  question without it → species lookup skipped.
- 🐛 **Not a prompt bug but found here:** the model resolved "tomorrow" from training data
  (produced a date in the wrong year). Fixed in code (`agent.py`): today's date is injected as a
  second system block after the cache breakpoint. Prompt versions stay date-free so the cached
  prefix never varies.
- Hypotheses 1–3 (ID verification, over-calling, hedging on sparse data) still to be tested —
  that's the Phase 6 eval's job, and V2 will respond to what it finds.

*V2 lands here after eval.*
