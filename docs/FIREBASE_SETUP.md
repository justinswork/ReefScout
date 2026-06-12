# Firebase setup — conversation history

ReefScout stores each signed-in user's conversations in **Cloud Firestore**, with **Google
sign-in** (Firebase Auth) for identity. The agent backend (FastAPI on Render) is untouched by
this — the browser talks to Firestore directly, gated by security rules. If Firebase isn't
configured, the app still runs; it just won't save history.

You only need to do this once. ~10 minutes.

## 1. Create a Firebase project
1. Go to <https://console.firebase.google.com/> and **Add project** (e.g. `reefscout`).
   (You can reuse an existing GCP project if you prefer.)
2. Google Analytics is optional — not needed here.

## 2. Enable Google sign-in
1. Build → **Authentication** → **Get started**.
2. **Sign-in method** → **Google** → enable → pick a support email → **Save**.

## 3. Create the Firestore database
1. Build → **Firestore Database** → **Create database**.
2. Start in **production mode** (we set explicit rules below), pick a region, **Enable**.

## 4. Apply the security rules
Firestore → **Rules** tab. Paste the contents of [`firestore.rules`](../firestore.rules) and
**Publish**. These rules let each user read/write only their own
`users/{uid}/conversations/*`, `users/{uid}/sightings/*`, and `users/{uid}/trips/*`, and deny
everything else.

> ⚠️ **If you set up history before the logbook feature:** the rules file gained `sightings` and
> `trips` collections. Re-paste and **Publish** the current `firestore.rules`, or logbook saves
> will fail with `permission-denied`.

## 5. Register a web app and set the config as env vars
1. Project settings (⚙️) → **Your apps** → **Web** (`</>`) → register an app (no Hosting needed).
2. Copy the `firebaseConfig` values it shows you.
3. Put them in your **environment**, not in source:
   - **Local:** add to `.env` (gitignored):
     ```
     FIREBASE_API_KEY=...
     FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
     FIREBASE_PROJECT_ID=your-project
     FIREBASE_APP_ID=...
     ```
   - **Render:** add the same four as service environment variables.

   The app serves them to the browser at runtime via the `/firebase-config.js` route
   (`app/main.py`). They're public client values, but injecting them at runtime keeps the
   repo free of keys (so secret scanners stay quiet) and lets you swap projects per
   environment.

### 5b. Restrict the API key (recommended)
The web API key is public by design, but you should still lock it down so it can't be abused:
APIs & Services → **Credentials** → your key → set **Application restrictions** to *HTTP
referrers* (add your Render domain and `http://localhost:8000/*`) and **API restrictions** to
just the Firebase APIs (Identity Toolkit, Token Service, Cloud Firestore). With this in place,
an exposed key is harmless.

## 6. Authorize your domains
Authentication → **Settings** → **Authorized domains** → add:
- `localhost` (for local dev — usually present by default)
- your Render hostname, e.g. `reefscout.onrender.com`

Sign-in popups are blocked on any domain not in this list.

## 7. Verify
- Local: run the app, click **Sign in**, complete the Google popup. Send a message, then open the
  **history** (clock) icon — your conversation should be listed. Reload and reopen it.
- Sign out and back in on another browser/device with the same Google account — your history
  follows you.

## What's stored (and what isn't)
- **Stored** per conversation: title, timestamps, and each message's role + text + the agent's
  tool-call trace. Agent reference-photo URLs are part of the message text, so they reload fine.
- **Not stored:** the raw bytes of photos *you* upload. They're sent to the model for that turn
  but kept out of Firestore (a base64 image would blow past Firestore's 1 MB per-document limit).
  A reloaded conversation shows your text and the agent's answer, not your original upload.
- **Scope:** history is per Google account, synced across devices. Signed-out use is ephemeral.
