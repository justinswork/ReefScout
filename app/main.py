"""
main.py — ReefScout's FastAPI backend.

Serves the Liquid-Glass chat UI and /chat, which runs the real agent loop
(app/agent.py): Claude + the MCP ocean-data tools, with a tool-call trace
returned alongside every reply.

If ANTHROPIC_API_KEY is not configured, /chat falls back to an explicit DEMO
MODE response (carrying `"demo": true`, surfaced as a badge in the UI) so the
frontend remains reviewable without a key. The deployed app always has a key.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()  # before anything reads ANTHROPIC_API_KEY

import os  # noqa: E402

from app.agent import ReefScoutAgent  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

agent: ReefScoutAgent | None = None


def _has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY", "").strip().startswith("sk-"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    if _has_api_key():
        agent = ReefScoutAgent()
        await agent.start()  # spawn MCP server subprocess once, reuse across requests
    yield
    if agent is not None:
        await agent.stop()
        agent = None


app = FastAPI(title="ReefScout", version="0.2.0", lifespan=lifespan)


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str


class ChatImage(BaseModel):
    media_type: str = Field(pattern="^image/(jpeg|png|webp|gif)$")
    # ~3 MB base64 ceiling per image; the UI downscales client-side before upload.
    data: str = Field(min_length=1, max_length=4_200_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = []
    images: list[ChatImage] = Field(default=[], max_length=3)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": "live" if agent is not None else "demo"}


@app.post("/chat")
async def chat(req: ChatRequest) -> dict:
    if agent is None:
        return _demo_response()

    # Cap history so a long session can't grow unbounded on the personal API key.
    history = [t.model_dump() for t in req.history[-12:]]
    images = [i.model_dump() for i in req.images] or None
    try:
        result = await agent.run(req.message, history, images)
    except Exception as exc:  # noqa: BLE001 - degrade to a readable chat error
        return {
            "reply": ("**Something went wrong on my end.** The live data sources and the "
                      f"model are usually quick to recover — please try again.\n\n`{exc}`"),
            "trace": [],
            "error": True,
        }
    return {"reply": result["reply"], "trace": result["trace"]}


def _demo_response() -> dict:
    return {
        "demo": True,
        "reply": (
            "**Demo mode** — no API key is configured on this server, so the agent isn't "
            "live. The deployed version of ReefScout answers with real ocean data: waves "
            "and water temperature from Open-Meteo, tides from NOAA, and recent wildlife "
            "sightings from iNaturalist."
        ),
        "trace": [],
    }


# Serve the UI. `html=True` makes / return static/index.html.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
