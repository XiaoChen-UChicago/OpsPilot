from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

import pandas as pd


LEAD_COLUMNS = [
    "company",
    "website",
    "contact_name",
    "title",
    "email",
    "industry",
    "employee_count",
    "country",
    "description",
    "source",
]


def normalize_url(value: object) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    parsed = urlparse(url)
    return url if parsed.netloc else ""


def normalize_email(value: object) -> str:
    email = str(value or "").strip().lower()
    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    return email if re.match(pattern, email) else ""


def canonicalize_leads(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a clean, predictable lead table without mutating the input."""
    clean = frame.copy()
    clean.columns = [str(column).strip().lower().replace(" ", "_") for column in clean.columns]

    for column in LEAD_COLUMNS:
        if column not in clean.columns:
            clean[column] = ""

    clean = clean[LEAD_COLUMNS]
    clean = clean.fillna("")
    for column in [c for c in LEAD_COLUMNS if c != "employee_count"]:
        clean[column] = clean[column].astype(str).str.strip()

    clean["website"] = clean["website"].map(normalize_url)
    clean["email"] = clean["email"].map(normalize_email)
    clean["employee_count"] = pd.to_numeric(clean["employee_count"], errors="coerce").fillna(0).astype(int)
    clean = clean[clean["company"].str.len() > 0]
    return clean.drop_duplicates(subset=["company", "email", "website"], keep="first").reset_index(drop=True)


def missing_fields(row: pd.Series, fields: Iterable[str] | None = None) -> list[str]:
    required = list(fields or ["website", "contact_name", "title", "email", "industry", "description"])
    return [field for field in required if not str(row.get(field, "")).strip()]

