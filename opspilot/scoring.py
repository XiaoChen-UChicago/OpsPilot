from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .models import missing_fields


DEFAULT_INDUSTRIES = [
    "Artificial Intelligence",
    "Software",
    "Financial Services",
    "Manufacturing",
]

BUYER_TITLES = [
    "founder",
    "chief executive",
    "ceo",
    "chief operating",
    "coo",
    "operations",
    "growth",
    "strategy",
    "innovation",
    "product",
]

INTENT_SIGNALS = [
    "automation",
    "manual",
    "workflow",
    "scale",
    "scaling",
    "agent",
    "artificial intelligence",
    "machine learning",
    "data pipeline",
    "operations",
]


@dataclass(frozen=True)
class ScoringProfile:
    target_industries: list[str] = field(default_factory=lambda: DEFAULT_INDUSTRIES.copy())
    min_employees: int = 10
    max_employees: int = 500
    industry_weight: int = 25
    size_weight: int = 20
    buyer_weight: int = 20
    intent_weight: int = 25
    completeness_weight: int = 10


def _contains_any(text: str, keywords: list[str]) -> list[str]:
    normalized = text.lower()
    return [keyword for keyword in keywords if keyword in normalized]


def score_lead(row: pd.Series, profile: ScoringProfile) -> dict[str, object]:
    score = 0
    reasons: list[str] = []
    gaps: list[str] = []

    industry = str(row.get("industry", ""))
    if industry in profile.target_industries:
        score += profile.industry_weight
        reasons.append(f"Target industry: {industry} (+{profile.industry_weight})")
    else:
        gaps.append("Industry is outside the current ICP")

    employees = int(row.get("employee_count", 0) or 0)
    if profile.min_employees <= employees <= profile.max_employees:
        score += profile.size_weight
        reasons.append(f"Company size fits {profile.min_employees}-{profile.max_employees} employees (+{profile.size_weight})")
    elif employees == 0:
        gaps.append("Employee count is unknown")
    else:
        gaps.append("Company size is outside the preferred range")

    title = str(row.get("title", ""))
    title_matches = _contains_any(title, BUYER_TITLES)
    if title_matches:
        score += profile.buyer_weight
        reasons.append(f"Relevant buyer role: {title} (+{profile.buyer_weight})")
    else:
        gaps.append("Contact is not a clear operational buyer")

    context = f"{row.get('description', '')} {row.get('industry', '')}"
    signals = _contains_any(context, INTENT_SIGNALS)
    if signals:
        score += profile.intent_weight
        reasons.append(f"Workflow signals: {', '.join(signals[:3])} (+{profile.intent_weight})")
    else:
        gaps.append("No explicit automation or scaling signal found")

    missing = missing_fields(row)
    completeness_ratio = max(0.0, (6 - len(missing)) / 6)
    completeness_points = round(profile.completeness_weight * completeness_ratio)
    score += completeness_points
    reasons.append(f"Profile completeness: {round(completeness_ratio * 100)}% (+{completeness_points})")
    if missing:
        gaps.append(f"Missing: {', '.join(missing)}")

    tier = "High" if score >= 75 else "Medium" if score >= 50 else "Low"
    return {
        "lead_score": min(score, 100),
        "priority_tier": tier,
        "score_reasons": " | ".join(reasons),
        "research_gaps": " | ".join(gaps),
    }


def score_dataframe(frame: pd.DataFrame, profile: ScoringProfile) -> pd.DataFrame:
    scored = frame.copy()
    results = [score_lead(row, profile) for _, row in scored.iterrows()]
    return pd.concat([scored.reset_index(drop=True), pd.DataFrame(results)], axis=1)

