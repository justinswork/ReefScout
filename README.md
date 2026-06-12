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

## Tech stack
Python · FastAPI · Anthropic Claude · Model Context Protocol (MCP) · deployed on Render.
