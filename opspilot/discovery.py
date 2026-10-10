from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlparse

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


# Search engines often return a roundup, job board, or market report when asked
# for companies. Those pages are useful research sources, but they are not
# accounts that can be added to a CRM. Keep the discovery table entity-first.
_GENERIC_TITLE_PATTERNS = (
    r"\btop\s*\d*\b",
    r"\bbest\b.*\bcompan(?:y|ies)\b",
    r"\bcompan(?:y|ies)\b.*\b(?:list|directory|ranked|based)\b",
    r"\b\d[\d,]*\+?\s+(?:ai|automation|workflow|software|tech|startup|company|job)",
    r"\bjobs?\b|\bjob listings?\b|\bcareers?\b|\bsalar(?:y|ies)\b",
    r"\b(?:guide|roundup|market map|report|trends?)\b",
)
_BLOCKED_HOSTS = {
    "indeed.com", "glassdoor.com", "ziprecruiter.com", "careerbuilder.com",
    "monster.com", "builtin.com", "simplyhired.com", "salary.com",
}
_PROFILE_HOSTS = {
    "cbinsights.com", "crunchbase.com", "pitchbook.com", "tracxn.com", "apollo.io",
    "wikipedia.org", "owler.com", "zoominfo.com", "growjo.com",
}
_NON_COMPANY_PATH_PARTS = {
    "jobs", "job", "search", "directory", "list", "rankings", "roundup",
    "careers", "career", "openings", "positions",
}
_GENERIC_LABEL_WORDS = {
    "automation", "consulting", "engineer", "engineering", "intern", "jobs", "platform",
    "services", "software", "solutions", "specialist", "technology", "technologies",
    "workflow",
}


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.").split(":", 1)[0]


def _is_blocked_host(host: str) -> bool:
    return any(host == blocked or host.endswith("." + blocked) for blocked in _BLOCKED_HOSTS)


def _is_profile_host(host: str) -> bool:
    return any(host == profile or host.endswith("." + profile) for profile in _PROFILE_HOSTS)


def _looks_like_list_page(title: str, url: str) -> bool:
    title_lower = title.lower()
    if any(re.search(pattern, title_lower) for pattern in _GENERIC_TITLE_PATTERNS):
        return True
    parsed = urlparse(url)
    path_parts = {part for part in parsed.path.lower().split("/") if part}
    if path_parts & _NON_COMPANY_PATH_PARTS:
        return True
    if "linkedin.com" in parsed.netloc.lower() and "/company/" not in parsed.path.lower():
        return True
    return _is_blocked_host(_host(url))


def _domain_brand(url: str) -> str:
    host = _host(url)
    if not host or _is_blocked_host(host):
        return ""
    parts = host.split(".")
    if len(parts) < 2:
        return ""
    slug = parts[-2]
    if slug in {"co", "com", "org", "net", "io", "ai", "app", "dev"} and len(parts) >= 3:
        slug = parts[-3]
    return re.sub(r"\s+", " ", slug.replace("-", " ").replace("_", " ")).strip().title()


def _company_name(title: str, url: str) -> str:
    """Extract a human company label, never a whole listicle headline."""
    candidate = re.split(r"\s+[|–—-]\s+", title, maxsplit=1)[0].strip()
    candidate = re.sub(r"^(?:about|official website of|company profile)\s*[:\-]?\s*", "", candidate, flags=re.I)
    candidate = re.sub(r"\s+\|.*$", "", candidate).strip()
    if candidate and not _looks_like_list_page(candidate, url):
        # A company label is short and should not read like a sentence or job.
        words = candidate.split()
        if len(words) <= 8 and not candidate.endswith((".", ":")):
            if _GENERIC_LABEL_WORDS.intersection(word.lower().strip(".,:&") for word in words):
                if _is_profile_host(_host(url)):
                    return candidate
                return _domain_brand(url) or candidate
            return candidate
    return _domain_brand(url)


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
    filters = [
        "Find individual companies with official company or product pages (one company per result), not listicles, job boards, or rankings.",
        goal.strip(),
    ]
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
        if not title or not url or _looks_like_list_page(title, url):
            continue
        company = _company_name(title, url)
        if not company:
            continue
        context = f"{title} {snippet}".lower()
        matches = [term for term in terms if term in context]
        score = min(100, 50 + len(matches) * 8)
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
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows).drop_duplicates(subset=["company"], keep="first")
    return frame.sort_values(["opportunity_score", "company"], ascending=[False, True]).head(max_results).reset_index(drop=True)
