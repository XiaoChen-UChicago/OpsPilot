# OpsPilot workspace mode

The public demo runs without an account and uses synthetic contacts. Workspace mode adds Google sign-in and an explicitly approved Gmail batch sender. The app detects the provider block in Streamlit secrets; once configured, the deployment becomes a private sign-in workspace.

## Configure Google sign-in and Gmail

1. In Google Cloud, create or select a project and enable the **Gmail API**.
2. Open **Google Auth Platform**, configure the consent screen, and add your own Google account as a test user while the app is in Testing.
3. Create an OAuth client with application type **Web application**.
4. Add the exact redirect URI `https://YOUR_APP.streamlit.app/oauth2callback` under **Authorized redirect URIs**.
5. Add the Gmail send scope `https://www.googleapis.com/auth/gmail.send` to the consent-screen scopes. The OpenID scopes in the example provide the signed-in user's identity.
6. Copy `.streamlit/secrets.example.toml` into Streamlit Community Cloud secrets and replace the placeholders with the Google client ID, client secret, and a long random cookie secret.
7. Keep the client secret and cookie secret in Streamlit secrets only. Never commit them to GitHub.

Streamlit uses OIDC for identity and exposes an access token only when `expose_tokens = ["access"]` is configured. OpsPilot keeps that token in memory for the current session and sends through the Gmail API only after the user explicitly approves a batch. The Gmail API call uses the signed-in account's mailbox and the `gmail.send` scope.

For a private test, keep the app in **Testing** and add each tester under **Test users**. If you later open it to many users, Google may require additional consent-screen review because Gmail scopes are sensitive.

The currently public demo is intentionally unauthenticated. Configure Google secrets in a separate Streamlit deployment if you want to keep the portfolio demo public while running a private sending workspace.

## Provider alternative: Microsoft Entra

Microsoft Entra remains supported. Replace the Google block with:

```toml
[auth.microsoft]
client_id = "your-entra-application-client-id"
client_secret = "your-entra-application-client-secret"
server_metadata_url = "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration"
client_kwargs = { scope = "openid profile email offline_access User.Read https://graph.microsoft.com/Mail.Send" }
```

Configure only one provider block at a time.

## Sending rules

- One approval sends at most 20 messages.
- Only records with a valid email address can be selected.
- The user must review the recipient list and approve the batch.
- The public demo never sends email; it only records a simulation.
- Production deployments should add organization policy, unsubscribe handling, consent/permission checks, rate limits, and persistent audit logs before real outreach.
