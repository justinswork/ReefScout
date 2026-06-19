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

from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()  # before anything reads ANTHROPIC_API_KEY

import json  # noqa: E402
import logging  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402

from app.agent import ReefScoutAgent  # noqa: E402

logger = logging.getLogger("reefscout")

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


# --- Abuse mitigation: in-memory rate limiting ---------------------------------------
# /chat spends a real (personal) Anthropic key on every call, so an unauthenticated,
# unthrottled public endpoint is a denial-of-wallet risk. These process-local counters
# are a backstop (Render's free tier is a single instance, so process-local state works).
# The HARD cost ceiling is the monthly spend limit set on the API key itself — see
# docs/SECURITY.md. All limits are tunable via env vars.
_CHAT_PER_IP_PER_MIN = int(os.environ.get("REEFSCOUT_CHAT_PER_IP_PER_MIN", "6"))
_CHAT_PER_IP_PER_HOUR = int(os.environ.get("REEFSCOUT_CHAT_PER_IP_PER_HOUR", "40"))
_CHAT_GLOBAL_PER_DAY = int(os.environ.get("REEFSCOUT_CHAT_GLOBAL_PER_DAY", "300"))
_RESOLVE_PER_IP_PER_MIN = int(os.environ.get("REEFSCOUT_RESOLVE_PER_IP_PER_MIN", "30"))
_RESOLVE_PER_IP_PER_HOUR = int(os.environ.get("REEFSCOUT_RESOLVE_PER_IP_PER_HOUR", "300"))

_ip_buckets: dict[str, dict[str, deque]] = {}
_chat_global: deque = deque()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")  # Render runs behind a proxy
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune(dq: deque, window: float, now: float) -> None:
    while dq and now - dq[0] > window:
        dq.popleft()


def _per_ip_ok(bucket: str, ip: str, per_min: int, per_hour: int, now: float) -> bool:
    ips = _ip_buckets.setdefault(bucket, {})
    if len(ips) > 5000:  # bound memory: drop IPs idle > 1h
        for k in [k for k, d in ips.items() if not d or now - d[-1] > 3600]:
            ips.pop(k, None)
    dq = ips.setdefault(ip, deque())
    _prune(dq, 3600, now)
    if len(dq) >= per_hour:
        return False
    if sum(1 for t in dq if now - t <= 60) >= per_min:
        return False
    dq.append(now)
    return True


def rate_limit_chat(request: Request) -> None:
    now = time.time()
    _prune(_chat_global, 86400, now)
    if len(_chat_global) >= _CHAT_GLOBAL_PER_DAY:
        raise HTTPException(status_code=429, detail="ReefScout has reached its daily request limit. Please try again tomorrow.")
    if not _per_ip_ok("chat", _client_ip(request), _CHAT_PER_IP_PER_MIN, _CHAT_PER_IP_PER_HOUR, now):
        raise HTTPException(status_code=429, detail="Too many requests — please wait a minute and try again.")
    _chat_global.append(now)


def rate_limit_resolve(request: Request) -> None:
    if not _per_ip_ok("resolve", _client_ip(request), _RESOLVE_PER_IP_PER_MIN, _RESOLVE_PER_IP_PER_HOUR, time.time()):
        raise HTTPException(status_code=429, detail="Too many requests — please slow down.")


class ChatTurn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=8000)  # bound prior-turn size (cost control)


class ChatImage(BaseModel):
    media_type: str = Field(pattern="^image/(jpeg|png|webp|gif)$")
    # ~3 MB base64 ceiling per image; the UI downscales client-side before upload.
    data: str = Field(min_length=1, max_length=4_200_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default=[], max_length=50)  # bound parse size; handler keeps last 12
    images: list[ChatImage] = Field(default=[], max_length=3)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "agent": "live" if agent is not None else "demo"}


def _derive_group(classification: dict) -> str:
    """Map a WoRMS classification to a logbook taxon group."""
    phylum = (classification.get("phylum") or "").lower()
    cls = (classification.get("class") or "").lower()
    order = (classification.get("order") or "").lower()
    if phylum == "mollusca":
        return "mollusk"
    if phylum == "echinodermata":
        return "echinoderm"
    if phylum == "cnidaria":
        return "cnidarian"
    if phylum == "arthropoda":  # marine arthropods in scope are effectively crustaceans
        return "crustacean"
    if phylum == "chordata":
        if cls in ("elasmobranchii", "chondrichthyes") or "shark" in order or "ray" in order:
            return "shark_ray"
        if cls in ("actinopterygii", "actinopteri", "teleostei"):
            return "fish"
        if cls == "reptilia" or order == "testudines":
            return "turtle"
        if cls == "mammalia":
            return "mammal"
        if cls == "aves":
            return "seabird"
        return "fish"
    return "other"


@app.get("/species/resolve")
async def resolve_species(name: str, _: None = Depends(rate_limit_resolve)) -> dict:
    """Look up authoritative details for a species the user logged by name.

    Used by the logbook so the user only types a name — scientific name, taxon group,
    and conservation status are filled in from WoRMS automatically. No LLM, no API key.
    """
    from app import ocean_data

    name = (name or "").strip()
    if not name:
        return {"found": False}
    search = await ocean_data.search_taxa(name, fuzzy=True, limit=1)
    if not search.get("found"):
        return {"found": False}

    cand = search["candidates"][0]
    classification = cand.get("classification", {})
    iucn = None
    if cand.get("aphia_id"):
        detail = await ocean_data.species_detail(cand["aphia_id"])
        if detail.get("found"):
            classification = detail.get("classification", classification)
            iucn = detail.get("iucn_status")

    # A reference photo for the logbook to default to (user can override with their own).
    # Prefer a binomial scientific name; for a genus-only WoRMS match (e.g. "moon jelly" -> the
    # genus "Aurelia"), the bare genus is ambiguous on iNaturalist, so use the user's name.
    sci_name = cand.get("scientific_name") or ""
    photo_query = sci_name if " " in sci_name.strip() else (name or sci_name)
    photo_url, photo_attribution = None, None
    photos = await ocean_data.species_images(photo_query, limit=1)
    if photos.get("found") and photos.get("images"):
        photo_url = photos["images"][0].get("photo_url")
        photo_attribution = photos["images"][0].get("attribution")

    return {
        "found": True,
        "scientific_name": cand.get("scientific_name"),
        "group": _derive_group(classification),
        "iucn_status": iucn,
        "photo_url": photo_url,
        "photo_attribution": photo_attribution,
    }


@app.post("/chat")
async def chat(req: ChatRequest, _: None = Depends(rate_limit_chat)) -> dict:
    if agent is None:
        return _demo_response()

    # Cap history so a long session can't grow unbounded on the personal API key.
    history = [t.model_dump() for t in req.history[-12:]]
    images = [i.model_dump() for i in req.images] or None
    try:
        result = await agent.run(req.message, history, images)
    except Exception:  # noqa: BLE001 - degrade to a readable chat error
        # Log the detail server-side; return a generic message (don't leak internals).
        logger.exception("agent.run failed")
        return {
            "reply": ("**Something went wrong on my end.** The live data sources and the "
                      "model are usually quick to recover — please try again in a moment."),
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


@app.get("/firebase-config.js")
async def firebase_config_js() -> Response:
    """Serve the Firebase web config from environment variables (FIREBASE_*).

    The config is public by design (it ships to the browser), but we inject it at
    runtime rather than committing it — so the repo carries no key, and access is
    governed by Firestore rules + Authorized domains + key restrictions. If the env
    vars are absent the app runs without auth/history (graceful).

    Defined before the static mount so it takes precedence over any local file.
    """
    cfg = {
        "apiKey": os.environ.get("FIREBASE_API_KEY", ""),
        "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN", ""),
        "projectId": os.environ.get("FIREBASE_PROJECT_ID", ""),
        "appId": os.environ.get("FIREBASE_APP_ID", ""),
    }
    body = f"window.REEFSCOUT_FIREBASE = {json.dumps(cfg)};\n"
    return Response(content=body, media_type="application/javascript", headers={"Cache-Control": "no-store"})


# Serve the UI. `html=True` makes / return static/index.html.
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
