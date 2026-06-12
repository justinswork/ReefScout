# Deploying ReefScout to Render

ReefScout runs as one FastAPI web service (it serves the UI, the agent's `/chat`, and the
`/firebase-config.js` + `/species/resolve` endpoints). Render's free tier is enough.

## What you need
- A [Render](https://render.com) account (sign in with GitHub — free).
- Your **Anthropic API key**.
- Your **Firebase web config** values (the four `FIREBASE_*` from `.env`).

## 1. Create the service from the blueprint
1. Render dashboard → **New +** → **Blueprint**.
2. Connect the **`justinswork/ReefScout`** repo (authorize Render for GitHub if prompted).
3. Render reads [`render.yaml`](../render.yaml) and proposes a free web service named `reefscout`.
   Click **Apply**.

(Manual alternative — **New +** → **Web Service** → pick the repo, then set:
Runtime `Python 3`, Build `pip install -r requirements.txt`,
Start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, Health check path `/health`.)

## 2. Set the environment variables
When prompted (or under the service's **Environment** tab), add:

| Key | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your personal Anthropic key |
| `FIREBASE_API_KEY` | from `.env` |
| `FIREBASE_AUTH_DOMAIN` | `reefscout-93243.firebaseapp.com` |
| `FIREBASE_PROJECT_ID` | `reefscout-93243` |
| `FIREBASE_APP_ID` | from `.env` |

`PYTHON_VERSION` and `REEFSCOUT_MODEL` are already set by the blueprint. Save → Render builds
and deploys. First build takes a few minutes; watch the **Logs** tab.

## 3. Point Firebase at the live domain
Once Render gives you a URL (e.g. `https://reefscout.onrender.com`):
1. **Firebase console → Authentication → Settings → Authorized domains → Add domain** → your
   Render hostname. (Google sign-in popups are blocked on unlisted domains.)
2. If you restricted the API key (recommended), add the Render URL to the key's **HTTP referrer**
   allowlist in Google Cloud Console too.

## 4. Verify
- Open the URL. It may take ~30–60 s to wake from sleep the first time (the UI shows a
  "waking up" message if a request times out) — this is expected on the free tier.
- Ask a planning question and an ID question; confirm the tool-trace panel shows real calls.
- Sign in with Google; log a sighting; reload and confirm it persisted.

## Notes
- **Free tier sleeps** after ~15 min idle and cold-starts on the next request (the agent's MCP
  subprocess spins up during that first request). The rubric explicitly allows a sleeping app
  that wakes up.
- **Cost:** hosting is free; live `/chat` calls bill your personal Anthropic key. The agent uses
  Sonnet and caps its tool loop, so cost per interaction is small.
- **Auto-deploy:** with the blueprint, pushes to `main` redeploy automatically.
