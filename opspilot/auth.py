from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import streamlit as st


def _auth_secrets() -> dict[str, Any]:
    """Return auth settings when Streamlit secrets are configured."""
    try:
        # Streamlit's secrets object supports mapping access, but older
        # runtimes do not consistently expose ``get`` for nested sections.
        configured = st.secrets["auth"]
        return {str(key): value for key, value in configured.items()} if configured else {}
    except Exception:
        return {}


def configured_provider() -> str | None:
    """Find the first named OIDC provider configured for the app."""
    auth = _auth_secrets()
    for name, value in auth.items():
        if isinstance(value, Mapping) and value.get("client_id") and value.get("server_metadata_url"):
            return str(name)
    return None


def auth_is_configured() -> bool:
    return configured_provider() is not None


def is_logged_in() -> bool:
    try:
        return bool(st.user.is_logged_in)
    except Exception:
        return False


def current_user() -> dict[str, str]:
    """Return a small, non-sensitive user profile for workspace scoping."""
    try:
        user = st.user
        email = str(getattr(user, "email", "") or user.get("email", ""))
        name = str(getattr(user, "name", "") or user.get("name", "") or email)
        subject = str(getattr(user, "sub", "") or user.get("sub", "") or email)
    except Exception:
        email = name = subject = ""
    return {"email": email, "name": name, "subject": subject}


def access_token() -> str:
    """Return the provider access token only when explicitly exposed by OIDC config."""
    try:
        tokens = st.user.tokens
        if isinstance(tokens, dict):
            return str(tokens.get("access", ""))
        return str(getattr(tokens, "access", "") or "")
    except Exception:
        return ""


def render_login(provider: str) -> None:
    st.title("Sign in to OpsPilot")
    st.write("Use your organization account to create a private workspace.")
    st.info("Your mailbox is only used after you explicitly approve a campaign send.")
    if st.button(f"Continue with {provider.title()}", type="primary"):
        st.login(provider)
