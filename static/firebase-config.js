// ReefScout — Firebase web config.
//
// This is the PUBLIC client config. It is NOT a secret: Firebase ships it to every
// browser, and access is controlled by Firestore security rules + Authorized domains,
// not by hiding these values. It is safe to commit.
//
// Replace the placeholders with your project's values, from:
//   Firebase console -> Project settings (gear) -> "Your apps" -> Web app -> SDK setup.
// Full walkthrough: docs/FIREBASE_SETUP.md
//
// Leave the placeholders as-is to run ReefScout WITHOUT saved history (chat still works;
// the "Sign in" button just explains that saving isn't configured).
window.REEFSCOUT_FIREBASE = {
  apiKey: "REPLACE_ME",
  authDomain: "REPLACE_ME.firebaseapp.com",
  projectId: "REPLACE_ME",
  appId: "REPLACE_ME",
};
