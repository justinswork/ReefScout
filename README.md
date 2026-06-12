# 🐠 ReefScout

**A location-aware marine field companion.** Ask whether a coastal spot is good for snorkeling
or tidepooling and what you'll likely see — or describe a creature you saw and let ReefScout
identify it and check whether that species can actually be there.

ReefScout is an **agentic** application: a Claude model decides which tools to call, chains them
based on the results, and verifies its own answers against authoritative marine data. The tools
are exposed through a real **MCP** server and backed by **free, no-API-key** live ocean data
sources.

### ▶️ Live app: **https://reefscout.onrender.com**
(Free tier — if it's been idle it may take ~30–60s to wake on the first request.)

> 🚧 **README in progress.** Full architecture, setup, and a worked example land in Phase 8.
> For now, see the planning docs:
> - [overview.md](overview.md) — what it is and how it works
> - [rubric.md](rubric.md) — project requirements (source of truth)
> - [plan.md](plan.md) — phased implementation plan
> - [docs/DEPLOY.md](docs/DEPLOY.md) · [docs/FIREBASE_SETUP.md](docs/FIREBASE_SETUP.md)

## Status
- [x] Planning docs
- [x] Repo scaffold
- [x] Live data layer
- [x] MCP server (7 tools)
- [x] Agent loop + backend
- [x] Prompts (v1 → v2 → v3)
- [x] Frontend (Liquid Glass UI)
- [x] Conversation history + naturalist logbook (Firebase)
- [x] Evaluation (9/9)
- [x] Deployment (Render — live)
- [ ] Documentation (full README + build log)

## Rubric checklist

Status of each project requirement (2 pts each). ✅ met · ◐ in progress.

| # | Requirement | Status | Where / how |
|---|---|---|---|
| 1 | Deployment | ✅ | Live at **https://reefscout.onrender.com** (free tier; wakes on load). Verified end-to-end. |
| 2 | Prompt engineering | ✅ | System prompt **v1 → v2 → v3** with documented rationale — [prompts/PROMPT_LOG.md](prompts/PROMPT_LOG.md). |
| 3 | System prompt(s) | ✅ | Purposeful role/scope/format prompt — [app/prompts.py](app/prompts.py). |
| 4 | Grounding | ✅ | Live conditions, tides, real sightings + authoritative WoRMS taxonomy injected via tools — [app/ocean_data.py](app/ocean_data.py). |
| 5 | MCP tool (definition) | ✅ | **Our own** FastMCP server, **7 tools** with name/description/schema — [app/mcp_server.py](app/mcp_server.py). Not a pre-built connector. |
| 6 | MCP tool (execution) | ✅ | Manual tool-call loop reads `tool_use`, dispatches over MCP, feeds results back — [app/agent.py](app/agent.py). Verified live. |
| 7 | Agentic behavior | ✅ | The model picks which tools to call, chains them, and decides when to stop (e.g. retries a failed geocode; skips the species tool when not asked). |
| 8 | Code on GitHub | ✅ | Public repo with an incremental, meaningful commit history. |
| 9 | Build log | ◐ | Captured across `PROMPT_LOG.md`, commit history, and `plan.md`; a consolidated `BUILD_LOG.md` is the last to-do. |
| 10 | Originality | ✅ | Marine field companion with **occurrence-based ID verification**, photo ID, and a naturalist **logbook** — not a generic chatbot. |
| 11 | Intellectual ownership | ✅ | Architecture and trade-offs documented in [overview.md](overview.md) and commit messages; author can explain failure modes. |
| 12 | Iteration | ✅ | Eval-driven: prompt v1 (7/8) → v2 (8/8), plus documented bug fixes (date grounding, photo mismatch). Draft→final feedback pass pending. |
| 13 | Evaluation | ✅ | 9 structured cases, **9/9**, with a documented earlier failure — [eval/run_eval.py](eval/run_eval.py), [eval/RESULTS.md](eval/RESULTS.md). |
| 14 | Documentation | ◐ | Architecture/setup/deploy docs exist ([overview.md](overview.md), [docs/](docs/)); the full README write-up + worked example is the remaining piece. |

## Tech stack
Python · FastAPI · Anthropic Claude · Model Context Protocol (MCP, our own server) · Firebase
(Auth + Firestore) · deployed on Render.
