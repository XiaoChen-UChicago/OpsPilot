from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import pandas as pd


DEFAULT_STATUS = "New"
PIPELINE_STATUSES = ["New", "Researched", "Qualified", "Contacted", "Meeting", "Nurture", "Disqualified"]


def database_path() -> Path:
    configured = os.getenv("OPSPILOT_DB_PATH", ".opspilot/opspilot.db")
    path = Path(configured)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path())
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            lead_id TEXT PRIMARY KEY,
            company TEXT NOT NULL,
            website TEXT,
            contact_name TEXT,
            title TEXT,
            email TEXT,
            industry TEXT,
            employee_count INTEGER,
            country TEXT,
            description TEXT,
            source TEXT,
            lead_score INTEGER,
            priority_tier TEXT,
            score_reasons TEXT,
            research_gaps TEXT,
            outreach_subject TEXT,
            outreach_draft TEXT,
            status TEXT NOT NULL DEFAULT 'New',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return connection


def lead_id(row: pd.Series) -> str:
    identity = "|".join(str(row.get(field, "")).strip().lower() for field in ["company", "website", "email"])
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def upsert_leads(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0

    connection = _connection()
    columns = [
        "company", "website", "contact_name", "title", "email", "industry", "employee_count",
        "country", "description", "source", "lead_score", "priority_tier", "score_reasons",
        "research_gaps", "outreach_subject", "outreach_draft",
    ]
    with connection:
        for _, row in frame.iterrows():
            values = {column: row.get(column, "") for column in columns}
            values["lead_id"] = lead_id(row)
            connection.execute(
                """
                INSERT INTO leads (
                    lead_id, company, website, contact_name, title, email, industry, employee_count,
                    country, description, source, lead_score, priority_tier, score_reasons,
                    research_gaps, outreach_subject, outreach_draft
                ) VALUES (
                    :lead_id, :company, :website, :contact_name, :title, :email, :industry, :employee_count,
                    :country, :description, :source, :lead_score, :priority_tier, :score_reasons,
                    :research_gaps, :outreach_subject, :outreach_draft
                )
                ON CONFLICT(lead_id) DO UPDATE SET
                    contact_name=excluded.contact_name,
                    title=excluded.title,
                    email=excluded.email,
                    industry=excluded.industry,
                    employee_count=excluded.employee_count,
                    country=excluded.country,
                    description=excluded.description,
                    source=excluded.source,
                    lead_score=excluded.lead_score,
                    priority_tier=excluded.priority_tier,
                    score_reasons=excluded.score_reasons,
                    research_gaps=excluded.research_gaps,
                    outreach_subject=excluded.outreach_subject,
                    outreach_draft=excluded.outreach_draft,
                    updated_at=CURRENT_TIMESTAMP
                """,
                values,
            )
    connection.close()
    return len(frame)


def load_leads() -> pd.DataFrame:
    connection = _connection()
    frame = pd.read_sql_query("SELECT * FROM leads ORDER BY lead_score DESC, updated_at DESC", connection)
    connection.close()
    return frame


def update_status(selected_lead_id: str, status: str) -> None:
    if status not in PIPELINE_STATUSES:
        raise ValueError(f"Unknown pipeline status: {status}")
    connection = _connection()
    with connection:
        connection.execute(
            "UPDATE leads SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE lead_id = ?",
            (status, selected_lead_id),
        )
    connection.close()

