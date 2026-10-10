from __future__ import annotations

import re
from typing import Iterable

import pandas as pd
import requests


class DiscoveryError(RuntimeError):
    pass


def _terms(goal: str) -> list[str]:
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "looking", "find",
        "companies", "company", "teams", "team", "want", "need", "help", "based", "using",
    }
    return [term for term in re.findall(r"[a-zA-Z0-9]+", goal.lower()) if len(term) > 2 and term not in stopwords]


def search_web(
    api_key: str,
    goal: str,
    industries: Iterable[str],
    countries: Iterable[str],
    size_range: tuple[int, int],
    max_results: int = 10,
) -> pd.DataFrame:
    """Search a configured web research provider and return source-backed opportunity leads."""
    if not api_key.strip():
        raise DiscoveryError("No live discovery API key is configured.")
    filters = [goal.strip()]
    if industries:
        filters.append("industries: " + ", ".join(industries))
    if countries:
        filters.append("locations: " + ", ".join(countries))
    filters.append(f"company size: {size_range[0]}-{size_range[1]} employees")
    query = " | ".join(part for part in filters if part)
    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as error:
        raise DiscoveryError(f"Live discovery request failed: {error}") from error

    terms = _terms(goal)
    rows: list[dict[str, object]] = []
    for result in payload.get("results", []):
        title = str(result.get("title", "")).strip()
        url = str(result.get("url", "")).strip()
        snippet = str(result.get("content", "")).strip()
        context = f"{title} {snippet}".lower()
        matches = [term for term in terms if term in context]
        score = min(100, 50 + len(matches) * 8)
        company = re.split(r"\s+[|–-]\s+", title, maxsplit=1)[0].strip() or title or url
        rows.append(
            {
                "company": company,
                "website": url,
                "contact_name": "",
                "title": "",
                "email": "",
                "industry": ", ".join(industries),
                "employee_count": 0,
                "country": ", ".join(countries),
                "description": snippet,
                "source": "Live web discovery",
                "opportunity_score": score,
                "match_reason": f"Matched goal terms: {', '.join(matches[:5]) or 'relevant search result'}",
                "recommended_action": "Review source and verify the right contact",
                "source_title": title,
                "source_url": url,
            }
        )
    return pd.DataFrame(rows).drop_duplicates(subset=["website"], keep="first") if rows else pd.DataFrame()
