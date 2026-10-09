from __future__ import annotations

import pandas as pd


VALUE_PROPS = {
    "Manufacturing": "reduce repetitive operational work and turn fragmented process data into clear next actions",
    "Financial Services": "make high-volume workflows easier to review, prioritize, and audit",
    "Healthcare": "reduce manual coordination while keeping people in control of sensitive decisions",
    "Artificial Intelligence": "add reliable workflow automation and transparent evaluation around AI systems",
    "Software": "automate repetitive go-to-market work without losing the context behind each decision",
    "Professional Services": "turn recurring research and client workflows into repeatable, measurable systems",
}


def generate_draft(row: pd.Series) -> tuple[str, str]:
    company = str(row.get("company", "your team"))
    name = str(row.get("contact_name", "")).strip()
    first_name = name.split()[0] if name else "there"
    industry = str(row.get("industry", ""))
    description = str(row.get("description", "")).strip()
    value_prop = VALUE_PROPS.get(
        industry,
        "identify repetitive work, prioritize the highest-value opportunities, and document why each action matters",
    )
    context = description[:180].rstrip(" .") if description else f"the work {company} is doing in {industry or 'its market'}"

    subject = f"Idea for scaling operations at {company}"
    body = (
        f"Hi {first_name},\n\n"
        f"I was looking at {context}. It made me curious about which research, qualification, or handoff steps still require the most manual work at {company}.\n\n"
        f"I built OpsPilot to {value_prop}. It combines public company research, transparent lead scoring, and review-ready outreach drafts in one workflow, while keeping a person in the approval loop.\n\n"
        "If this is relevant to your current priorities, I would be glad to share a short walkthrough and compare notes on where automation could be useful.\n\n"
        "Best,\nXiao"
    )
    return subject, body


def create_outreach_columns(frame: pd.DataFrame) -> pd.DataFrame:
    drafted = frame.copy()
    drafts = [generate_draft(row) for _, row in drafted.iterrows()]
    drafted["outreach_subject"] = [subject for subject, _ in drafts]
    drafted["outreach_draft"] = [body for _, body in drafts]
    return drafted

