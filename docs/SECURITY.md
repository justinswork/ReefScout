# Security review

A pre-release audit of ReefScout as a **public, unauthenticated** web app. The dominant risk in
an app like this isn't data theft (there's little sensitive data) — it's **abuse of the owner's
resources**: the `/chat` endpoint spends a personal Anthropic API key on every call.

## Threat model
- **Anyone on the internet** can POST to `/chat` and `/species/resolve` (no login required — by
  design, so a reviewer can try the app).
- **`/chat` costs real money** per call (Claude + a multi-tool agent loop).
- **Signed-in users** (any Google account) can read/write **only their own** Firestore subtree.
- The Anthropic key lives **only server-side**; the Firebase web key is public by design.

## Findings

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | **Critical** | Denial-of-wallet: `/chat` was unauthenticated and unthrottled, so a script could run up the owner's Anthropic bill (and use the key as a free LLM proxy). | **Mitigated** (rate limits) + **action required** (spend cap) |
| 2 | High | Oversized requests: prior-turn `content` and history length were unbounded → large prompts = cost. | **Fixed** |
| 3 | Medium | `/chat` errors echoed the raw exception string to the client (info disclosure). | **Fixed** |
| 4 | Medium | `/species/resolve` was unthrottled — could be used to hammer/proxy WoRMS + iNaturalist (risking the server IP getting blocked). | **Fixed** (rate limit) |
| 5 | Medium | A signed-in user could spam many/large Firestore docs in their own space (quota abuse). | **Accepted / recommend** |

### 1 — Denial-of-wallet (the one that matters)
Mitigations now in code (`app/main.py`), all tunable via env vars:
- **Per-IP:** 6 requests/min and 40/hour on `/chat`.
- **Global backstop:** 300 `/chat` requests/day across all users.
- Returns HTTP 429 with a friendly message; the UI surfaces it.

These are process-local counters (Render's free tier is a single instance) — a deterrent, not a
hard boundary (IPs can be rotated). **The real ceiling is operational and you must set it:**

> ⭐ **Set a monthly spend limit on the Anthropic API key** in the Anthropic Console
> (Billing → usage limits). This caps the absolute worst case regardless of how the app is abused.

### 2 — Input bounds (fixed)
`message` ≤ 2000 chars; each history `content` ≤ 8000; history ≤ 50 turns (handler keeps last 12);
≤ 3 images, ≤ ~3 MB each (downscaled client-side first).

### 3 — Error disclosure (fixed)
`/chat` now logs the exception server-side and returns a generic message, instead of embedding the
raw exception text in the reply.

### 4 — Resolve endpoint (fixed)
`/species/resolve` is rate-limited per IP (30/min, 300/hour). It's keyless (no cost to the owner),
but throttling protects the upstream free APIs and the server's reputation with them.

### 5 — Firestore quota abuse (accepted)
Rules scope every user to their own `users/{uid}/…` subtree with a deny-all default, so one user
can't touch another's data. A user *could* fill their own space with junk. Mitigation: **keep the
project on the Firebase Spark (free) plan**, whose hard quotas cap usage with no billing — abuse
degrades to "quota exceeded," never a charge. Optional future hardening: add field-size limits to
`firestore.rules`.

## Reviewed and clean
- **XSS:** all rendered output is HTML-escaped (`escapeHtml`/`escapeAttr`); inline images are
  restricted to `https://` URLs; user data is per-user (Firestore rules), so there's no stored-XSS
  path to other users — only self-view.
- **SSRF:** no user-controlled URLs are fetched server-side. Tools take a place name / coordinates /
  species name, passed as **encoded query params** to a fixed set of APIs.
- **Injection:** no SQL, no shell, no `eval`. External calls use `httpx` params (encoded). The MCP
  tools are **read-only** — no file, database, or shell side effects.
- **Secrets:** the Anthropic key is server-side only and never returned to the client; `.env` is
  gitignored; the Firebase web config is public by design and injected from env at runtime (not
  committed). `/health` exposes only liveness.
- **Auth/data isolation:** `firestore.rules` — each user reads/writes only their own subtree;
  everything else denied.

## Operational checklist (do before/at public release)
- [ ] **Set a monthly spend limit on the Anthropic API key** (the hard cost ceiling). ⭐
- [ ] **Restrict the Firebase API key** in Google Cloud (HTTP referrers + API restrictions).
- [ ] Add the Render domain to **Firebase → Authentication → Authorized domains**.
- [ ] Keep Firebase on the **Spark (free)** plan so quota abuse can't incur charges.
- [ ] (Optional) Tune the rate-limit env vars (`REEFSCOUT_CHAT_*`, `REEFSCOUT_RESOLVE_*`) on Render.
