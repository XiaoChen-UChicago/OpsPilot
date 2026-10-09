from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd
import requests
from bs4 import BeautifulSoup


INDUSTRY_KEYWORDS = {
    "Artificial Intelligence": ["artificial intelligence", "machine learning", "ai agent", "llm"],
    "Financial Services": ["fintech", "financial services", "payments", "banking", "insurance"],
    "Manufacturing": ["manufacturing", "factory", "industrial", "supply chain", "robotics"],
    "Healthcare": ["healthcare", "clinical", "patient", "medical", "health tech"],
    "Software": ["software", "saas", "developer", "cloud platform", "api"],
    "Professional Services": ["consulting", "advisory", "professional services", "agency"],
}


@dataclass(frozen=True)
class WebsiteResearch:
    title: str = ""
    description: str = ""
    industry: str = ""
    evidence: str = ""
    status: str = "Not researched"


def infer_industry(text: str) -> str:
    normalized = text.lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return industry
    return ""


def research_website(url: str, timeout_seconds: int = 6) -> WebsiteResearch:
    """Collect a small amount of public homepage context; no crawling or personal data."""
    if not url:
        return WebsiteResearch(status="No website supplied")

    try:
        response = requests.get(
            url,
            timeout=timeout_seconds,
            headers={"User-Agent": "OpsPilot/0.1 (portfolio research demo)"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return WebsiteResearch(status=f"Research unavailable: {exc.__class__.__name__}")

    soup = BeautifulSoup(response.text, "html.parser")
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    description = meta.get("content", "").strip() if meta else ""
    visible_text = " ".join(soup.get_text(" ", strip=True).split())
    evidence = " ".join(part for part in [title, description, visible_text[:700]] if part)

    return WebsiteResearch(
        title=title[:180],
        description=(description or visible_text[:320])[:500],
        industry=infer_industry(evidence),
        evidence=evidence[:900],
        status="Researched from public homepage",
    )


def enrich_row(row: pd.Series) -> dict[str, object]:
    enriched = row.to_dict()
    result = research_website(str(row.get("website", "")))
    if not str(enriched.get("description", "")).strip() and result.description:
        enriched["description"] = result.description
    if not str(enriched.get("industry", "")).strip() and result.industry:
        enriched["industry"] = result.industry
    enriched["research_status"] = result.status
    enriched["research_evidence"] = result.evidence
    return enriched


def enrich_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([enrich_row(row) for _, row in frame.iterrows()])

