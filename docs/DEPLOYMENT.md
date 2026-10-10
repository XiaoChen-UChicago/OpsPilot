# OpsPilot workspace mode

The public demo runs without an account and uses synthetic contacts. Workspace mode adds OIDC sign-in and an explicitly approved email batch sender.

## Configure Microsoft sign-in

1. Create an application registration in Microsoft Entra ID.
2. Add the redirect URI `https://YOUR_APP.streamlit.app/oauth2callback` as a web redirect URI.
3. Grant delegated permissions for `openid`, `profile`, `email`, `offline_access`, `User.Read`, and `Mail.Send`.
4. Copy `.streamlit/secrets.example.toml` into Streamlit Community Cloud secrets and replace the placeholders.
5. Keep the client secret and cookie secret in Streamlit secrets only. Never commit them to GitHub.

Streamlit uses OIDC for identity and exposes an access token only when `expose_tokens = ["access"]` is configured. OpsPilot keeps that token in memory for the current session and sends through Microsoft Graph only after the user explicitly approves a batch.

## Sending rules

- One approval sends at most 20 messages.
- Only records with a valid email address can be selected.
- The user must review the recipient list and approve the batch.
- The public demo never sends email; it only records a simulation.
- Production deployments should add organization policy, unsubscribe handling, consent/permission checks, rate limits, and persistent audit logs before real outreach.
