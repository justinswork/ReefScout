"""
main.py — ReefScout's FastAPI backend.

Serves the Liquid-Glass chat UI and the /chat endpoint the UI talks to.

NOTE (Phase 3 pending): /chat currently runs in DEMO MODE — it returns a canned
response with a simulated tool trace so the UI can be developed and reviewed
before the agent loop exists. The response carries `"demo": true` and the UI
displays a visible "demo mode" badge; nothing here pretends to be the real
agent. Phase 3 replaces the stub body with the MCP-client agent loop.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI(title="ReefScout", version="0.1.0")

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = []


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "demo_mode": True}


@app.post("/chat")
async def chat(req: ChatRequest) -> dict:
    # ------------------------------------------------------------------
    # DEMO MODE STUB — replaced by the real MCP agent loop in Phase 3.
    # Returns the exact response shape the real agent will produce, so the
    # UI is built against the final contract.
    # ------------------------------------------------------------------
    return {
        "demo": True,
        "reply": (
            "**Demo mode** — the ReefScout agent isn't connected yet, so this is a "
            "placeholder reply showing how answers will look.\n\n"
            "Once live, I'll check real conditions for your question:\n"
            "- **Waves & water temp** from Open-Meteo Marine\n"
            "- **Tides** from the nearest NOAA station\n"
            "- **What you're likely to see** from iNaturalist sightings\n\n"
            "Try the trace panel below this message to see how tool calls will be displayed."
        ),
        "trace": [
            {
                "tool": "geocode_place",
                "args": {"place": "La Jolla"},
                "summary": "→ 32.85, -117.27 (San Diego, California)",
                "ms": 312,
            },
            {
                "tool": "get_marine_conditions",
                "args": {"latitude": 32.85, "longitude": -117.27, "date": "2026-06-13"},
                "summary": "→ waves 1.2 m max · swell 1.0 m · water 21.5 °C",
                "ms": 489,
            },
            {
                "tool": "get_tides",
                "args": {"latitude": 32.85, "longitude": -117.27, "date": "2026-06-13"},
                "summary": "→ low −1.2 ft 02:49 · high 6.8 ft 20:10 (station: La Jolla, 1.1 km)",
                "ms": 641,
            },
        ],
    }


# Serve the UI. `html=True` makes / return static/index.html.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
