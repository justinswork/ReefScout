# 🐠 ReefScout

**A location-aware marine field companion.** Ask whether a coastal spot is good for snorkeling
or tidepooling and what you'll likely see — or describe a creature you saw and let ReefScout
identify it and check whether that species can actually be there.

ReefScout is an **agentic** application: a Claude model decides which tools to call, chains them
based on the results, and verifies its own answers against authoritative marine data. The tools
are exposed through a real **MCP** server and backed by **free, no-API-key** live ocean data
sources.

> 🚧 **Work in progress.** This README is a stub; full architecture, setup, and example
> interactions land in Phase 8. For now, see the planning docs:
> - [overview.md](overview.md) — what it is and how it works
> - [rubric.md](rubric.md) — project requirements (source of truth)
> - [plan.md](plan.md) — phased implementation plan

## Status
- [x] Planning docs
- [x] Repo scaffold
- [ ] Live data layer
- [ ] MCP server
- [ ] Agent loop + backend
- [ ] Prompts (v1 → v2)
- [ ] Frontend
- [ ] Evaluation
- [ ] Deployment
- [ ] Documentation

## Tech stack
Python · FastAPI · Anthropic Claude · Model Context Protocol (MCP) · deployed on Render.
