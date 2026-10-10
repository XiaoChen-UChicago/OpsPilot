from __future__ import annotations

from io import StringIO
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from opspilot.enrichment import enrich_dataframe
from opspilot.models import LEAD_COLUMNS, canonicalize_leads
from opspilot.outreach import create_outreach_columns, generate_draft
from opspilot.scoring import DEFAULT_INDUSTRIES, ScoringProfile, score_dataframe
from opspilot.storage import PIPELINE_STATUSES, load_leads, update_status, upsert_leads


ROOT = Path(__file__).parent
SAMPLE_DATA = ROOT / "data" / "sample_leads.csv"

st.set_page_config(
    page_title="OpsPilot",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root { --ink: #102a43; --muted: #526579; --accent: #0f766e; --accent-dark: #0b5f59; --surface: #f6f8fb; --line: #d9e2ec; }
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] { background: linear-gradient(180deg, #fbfcfe 0%, #f5f8fb 100%) !important; color: var(--ink) !important; }
    .block-container { padding-top: 2.1rem; max-width: 1240px; }
    [data-testid="stHeader"] { background: rgba(251, 252, 254, .88) !important; }
    [data-testid="stSidebar"] { background: #111827 !important; }
    [data-testid="stSidebar"] * { color: #e6edf5 !important; }
    [data-testid="stSidebar"] hr { border-color: rgba(230, 237, 245, .18) !important; }
    .hero {
        padding: 1.3rem 1.5rem; border: 1px solid #d9e2ec; border-radius: 18px;
        background: linear-gradient(135deg, #ffffff 0%, #effcf9 100%);
        box-shadow: 0 10px 30px rgba(16, 42, 67, .06); margin-bottom: 1rem;
    }
    .hero h1 { color: var(--ink); margin: 0 0 .35rem 0; letter-spacing: -.03em; }
    .hero p { color: var(--muted); margin: 0; font-size: 1.04rem; }
    .eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: .12em; font-weight: 700; font-size: .74rem; }
    div[data-testid="stMetric"] { background: #ffffff !important; border: 1px solid var(--line); padding: .9rem; border-radius: 14px; box-shadow: 0 4px 14px rgba(16, 42, 67, .04); }
    div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] p { color: #526579 !important; }
    div[data-testid="stMetricValue"] { color: var(--ink) !important; }
    div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 12px; overflow: hidden; background: #ffffff !important; }
    .stCaption, [data-testid="stCaptionContainer"] { color: #526579 !important; }
    .stTextInput label, .stTextArea label, .stNumberInput label, .stSelectbox label, .stMultiSelect label, .stSlider label, .stFileUploader label { color: #334e68 !important; font-weight: 600 !important; }
    [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div, [data-testid="stNumberInput"] input { background: #ffffff !important; color: var(--ink) !important; border-color: #bcccdc !important; }
    [data-baseweb="input"] input, [data-baseweb="textarea"] textarea, [data-testid="stNumberInput"] input { color: var(--ink) !important; -webkit-text-fill-color: var(--ink) !important; }
    [data-baseweb="input"] input::placeholder, [data-baseweb="textarea"] textarea::placeholder { color: #829ab1 !important; opacity: 1 !important; }
    [data-testid="stForm"] { background: rgba(255,255,255,.84); border: 1px solid var(--line); border-radius: 16px; padding: 1rem 1.1rem .2rem; box-shadow: 0 8px 24px rgba(16, 42, 67, .05); }
    button[kind="primary"], button[kind="primaryFormSubmit"], button[data-testid="baseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] { background: var(--accent) !important; border-color: var(--accent) !important; color: #ffffff !important; }
    button[kind="primary"] *, button[kind="primaryFormSubmit"] *, button[data-testid="baseButton-primary"] *, button[data-testid="stBaseButton-primaryFormSubmit"] * { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
    button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover, button[data-testid="baseButton-primary"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover { background: var(--accent-dark) !important; border-color: var(--accent-dark) !important; }
    button:not([kind="primary"]):not([kind="primaryFormSubmit"]):not([data-testid="baseButton-primary"]):not([data-testid="stBaseButton-primaryFormSubmit"]):not([data-testid="manage-app-button"]) { color: #334e68 !important; border-color: #bcccdc !important; background: #ffffff !important; }
    button:not([kind="primary"]):not([kind="primaryFormSubmit"]):not([data-testid="baseButton-primary"]):not([data-testid="stBaseButton-primaryFormSubmit"]):not([data-testid="manage-app-button"]) * { color: #334e68 !important; -webkit-text-fill-color: #334e68 !important; }
    [data-testid="stSidebar"] button:not([kind="primary"]):not([kind="primaryFormSubmit"]) { color: #e6edf5 !important; border-color: rgba(230,237,245,.35) !important; background: transparent !important; }
    [data-testid="stSidebar"] button:not([kind="primary"]):not([kind="primaryFormSubmit"]) * { color: #e6edf5 !important; -webkit-text-fill-color: #e6edf5 !important; }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] { background: transparent !important; background-color: transparent !important; color: #e6edf5 !important; border-color: rgba(230,237,245,.35) !important; }
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] * { color: #e6edf5 !important; -webkit-text-fill-color: #e6edf5 !important; }
    [data-baseweb="tab-list"] { gap: .45rem; border-bottom: 1px solid var(--line); }
    [data-baseweb="tab"] { color: #526579 !important; font-weight: 600 !important; }
    [data-baseweb="tab"][aria-selected="true"] { color: var(--accent) !important; border-bottom-color: var(--accent) !important; }
    .signal { border-left: 4px solid #0f766e; padding: .7rem 1rem; background: #f0fdfa; border-radius: 0 10px 10px 0; }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_sample() -> pd.DataFrame:
    return canonicalize_leads(pd.read_csv(SAMPLE_DATA))


def ensure_scored(frame: pd.DataFrame, profile: ScoringProfile | None = None) -> pd.DataFrame:
    clean = canonicalize_leads(frame)
    scored = score_dataframe(clean, profile or ScoringProfile())
    return create_outreach_columns(scored)


if "leads" not in st.session_state:
    st.session_state.leads = ensure_scored(load_sample())

with st.sidebar:
    st.markdown("### ◈ OpsPilot")
    st.caption("AI-assisted lead research and workflow automation")
    st.markdown("---")
    st.markdown("**Workflow**")
    st.markdown("1. Import leads\n2. Add public context\n3. Score with visible rules\n4. Review outreach drafts\n5. Manage the pipeline")
    st.markdown("---")
    st.info("Demo mode uses synthetic contacts. Drafts are never sent automatically.")
    if st.button("Reset demo data", use_container_width=True):
        st.session_state.leads = ensure_scored(load_sample())
        st.rerun()

st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">Human-in-the-loop revenue operations</div>
      <h1>OpsPilot</h1>
      <p>Research accounts, explain every priority score, and prepare review-ready outreach from one transparent workflow.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

dashboard_tab, intake_tab, research_tab, outreach_tab, crm_tab, method_tab = st.tabs(
    ["Command Center", "Lead Intake", "Research & Score", "Outreach Studio", "CRM Pipeline", "Methodology"]
)

with dashboard_tab:
    leads = st.session_state.leads
    high_priority = leads[leads["priority_tier"] == "High"]
    average_score = round(float(leads["lead_score"].mean()), 1) if not leads.empty else 0
    complete_profiles = int((leads["research_gaps"].str.len() == 0).sum()) if not leads.empty else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Accounts", len(leads))
    col2.metric("High priority", len(high_priority))
    col3.metric("Average fit score", average_score)
    col4.metric("Complete profiles", complete_profiles)

    st.subheader("Try the workflow")
    st.caption("Add one account here to see it normalized, scored, and added to the pipeline. Use **Lead Intake** for CSV uploads and richer fields.")
    with st.form("quick_add_account"):
        quick_col1, quick_col2, quick_col3 = st.columns([1.2, 1, 1])
        with quick_col1:
            quick_company = st.text_input("Company *", placeholder="Example AI")
        with quick_col2:
            quick_industry = st.text_input("Industry", placeholder="Software")
        with quick_col3:
            quick_website = st.text_input("Website", placeholder="https://example.com")
        quick_submit = st.form_submit_button("Add account and score", type="primary", use_container_width=True)
    if quick_submit:
        if not quick_company.strip():
            st.warning("Enter a company name first.")
        else:
            quick_lead = pd.DataFrame([{
                "company": quick_company.strip(), "website": quick_website.strip(),
                "contact_name": "", "title": "", "email": "", "industry": quick_industry.strip(),
                "employee_count": 0, "country": "", "description": "", "source": "Quick start",
            }])
            combined = pd.concat([st.session_state.leads[LEAD_COLUMNS], quick_lead], ignore_index=True)
            st.session_state.leads = ensure_scored(combined)
            st.success(f"Added {quick_company.strip()} and recalculated its fit score.")
            st.rerun()

    chart_col, table_col = st.columns([0.9, 1.5])
    with chart_col:
        st.subheader("Pipeline opportunity")
        tier_order = ["High", "Medium", "Low"]
        counts = leads["priority_tier"].value_counts().reindex(tier_order, fill_value=0).reset_index()
        counts.columns = ["Priority", "Accounts"]
        figure = px.bar(
            counts,
            x="Priority",
            y="Accounts",
            color="Priority",
            color_discrete_map={"High": "#0f766e", "Medium": "#f59e0b", "Low": "#94a3b8"},
        )
        figure.update_layout(showlegend=False, height=320, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(figure, use_container_width=True)

    with table_col:
        st.subheader("Highest-priority accounts")
        display_columns = ["company", "industry", "contact_name", "title", "lead_score", "priority_tier"]
        st.dataframe(
            leads.sort_values("lead_score", ascending=False)[display_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                "lead_score": st.column_config.ProgressColumn("Fit score", min_value=0, max_value=100),
                "priority_tier": "Priority",
            },
        )

    st.markdown('<div class="signal"><b>Decision support, not autopilot.</b> Every score shows its evidence and gaps before a person decides what happens next.</div>', unsafe_allow_html=True)

with intake_tab:
    st.subheader("Bring leads into one clean workflow")
    st.caption("Upload a CSV, add an account manually, or start with the synthetic demonstration dataset.")
    upload_col, manual_col = st.columns(2)

    with upload_col:
        st.markdown("#### CSV import")
        uploaded = st.file_uploader("Upload lead data", type=["csv"])
        st.caption("Recommended columns: " + ", ".join(LEAD_COLUMNS))
        template = pd.DataFrame(columns=LEAD_COLUMNS).to_csv(index=False)
        st.download_button("Download CSV template", template, "opspilot_lead_template.csv", "text/csv")
        if uploaded is not None:
            imported = canonicalize_leads(pd.read_csv(uploaded))
            st.dataframe(imported, use_container_width=True, hide_index=True)
            if st.button("Add imported leads", type="primary"):
                combined = pd.concat([st.session_state.leads[LEAD_COLUMNS], imported], ignore_index=True)
                st.session_state.leads = ensure_scored(combined)
                st.success(f"Added {len(imported)} account(s).")
                st.rerun()

    with manual_col:
        st.markdown("#### Manual account")
        with st.form("manual_lead"):
            company = st.text_input("Company *")
            website = st.text_input("Website")
            contact_name = st.text_input("Contact name")
            title = st.text_input("Role/title")
            email = st.text_input("Email")
            industry = st.text_input("Industry")
            employee_count = st.number_input("Employees", min_value=0, value=0, step=1)
            description = st.text_area("What does the company do?")
            submitted = st.form_submit_button("Add account", type="primary")
        if submitted and company.strip():
            new_lead = pd.DataFrame(
                [{
                    "company": company, "website": website, "contact_name": contact_name,
                    "title": title, "email": email, "industry": industry,
                    "employee_count": employee_count, "country": "",
                    "description": description, "source": "Manual entry",
                }]
            )
            combined = pd.concat([st.session_state.leads[LEAD_COLUMNS], new_lead], ignore_index=True)
            st.session_state.leads = ensure_scored(combined)
            st.success(f"Added {company}.")
            st.rerun()

with research_tab:
    st.subheader("Define the ideal customer profile")
    config_col, result_col = st.columns([0.8, 1.6])

    with config_col:
        target_industries = st.multiselect(
            "Target industries",
            options=sorted(set(st.session_state.leads["industry"].tolist() + DEFAULT_INDUSTRIES)),
            default=DEFAULT_INDUSTRIES,
        )
        minimum, maximum = st.slider("Preferred company size", 1, 2000, (10, 500))
        st.markdown("#### Score weights")
        industry_weight = st.slider("Industry fit", 0, 40, 25)
        size_weight = st.slider("Company size", 0, 40, 20)
        buyer_weight = st.slider("Buyer relevance", 0, 40, 20)
        intent_weight = st.slider("Automation signal", 0, 40, 25)
        completeness_weight = st.slider("Data completeness", 0, 25, 10)
        total_weight = industry_weight + size_weight + buyer_weight + intent_weight + completeness_weight
        st.caption(f"Maximum raw score: {total_weight}. Scores are capped at 100.")

        profile = ScoringProfile(
            target_industries=target_industries,
            min_employees=minimum,
            max_employees=maximum,
            industry_weight=industry_weight,
            size_weight=size_weight,
            buyer_weight=buyer_weight,
            intent_weight=intent_weight,
            completeness_weight=completeness_weight,
        )
        if st.button("Recalculate priorities", type="primary", use_container_width=True):
            st.session_state.leads = ensure_scored(st.session_state.leads[LEAD_COLUMNS], profile)
            st.success("Priorities recalculated with the visible rules above.")
            st.rerun()

        if st.button("Research public homepages", use_container_width=True):
            with st.spinner("Reading supplied company homepages..."):
                enriched = enrich_dataframe(st.session_state.leads[LEAD_COLUMNS])
                st.session_state.leads = ensure_scored(enriched[LEAD_COLUMNS], profile)
            st.success("Public website context added where available.")
            st.rerun()

    with result_col:
        st.markdown("#### Explainable ranking")
        selected_company = st.selectbox("Inspect an account", st.session_state.leads["company"].tolist())
        selected = st.session_state.leads[st.session_state.leads["company"] == selected_company].iloc[0]
        metric_a, metric_b, metric_c = st.columns(3)
        metric_a.metric("Fit score", int(selected["lead_score"]))
        metric_b.metric("Priority", selected["priority_tier"])
        metric_c.metric("Employees", int(selected["employee_count"]) or "Unknown")
        st.markdown("**Why this account received its score**")
        for reason in str(selected["score_reasons"]).split(" | "):
            st.success(reason)
        if selected["research_gaps"]:
            st.markdown("**What should be verified next**")
            for gap in str(selected["research_gaps"]).split(" | "):
                st.warning(gap)

with outreach_tab:
    st.subheader("Prepare outreach for human review")
    st.caption("OpsPilot drafts messages but never sends them. A person verifies the facts, tone, and recipient first.")
    selected_company = st.selectbox(
        "Choose an account",
        st.session_state.leads.sort_values("lead_score", ascending=False)["company"].tolist(),
        key="outreach_company",
    )
    selected = st.session_state.leads[st.session_state.leads["company"] == selected_company].iloc[0]
    subject, body = generate_draft(selected)
    context_col, draft_col = st.columns([0.8, 1.3])
    with context_col:
        st.markdown("#### Account context")
        st.write(f"**Industry:** {selected['industry'] or 'Unknown'}")
        st.write(f"**Contact:** {selected['contact_name'] or 'Unknown'} — {selected['title'] or 'Unknown role'}")
        st.write(f"**Score:** {selected['lead_score']} ({selected['priority_tier']})")
        st.write(f"**Source:** {selected['source']}")
        with st.expander("Scoring evidence"):
            st.write(selected["score_reasons"])
    with draft_col:
        st.markdown("#### Review-ready draft")
        st.text_input("Subject", value=subject)
        st.text_area("Message", value=body, height=320)
        st.caption("Before use: verify every company claim, add a genuine personal observation, and obtain approval before sending.")

with crm_tab:
    st.subheader("Manage a lightweight local pipeline")
    save_col, export_col = st.columns([1, 1])
    with save_col:
        if st.button("Save current accounts to CRM", type="primary", use_container_width=True):
            saved = upsert_leads(st.session_state.leads)
            st.success(f"Saved {saved} account(s) to the local CRM.")
    with export_col:
        export_data = st.session_state.leads.to_csv(index=False)
        st.download_button(
            "Export scored accounts",
            export_data,
            "opspilot_scored_leads.csv",
            "text/csv",
            use_container_width=True,
        )

    stored = load_leads()
    if stored.empty:
        st.info("Save the current accounts to start the CRM pipeline.")
    else:
        update_col, pipeline_col = st.columns([0.7, 1.5])
        with update_col:
            labels = {f"{row['company']} · {row['status']}": row["lead_id"] for _, row in stored.iterrows()}
            selected_label = st.selectbox("Account", labels.keys())
            current_row = stored[stored["lead_id"] == labels[selected_label]].iloc[0]
            current_index = PIPELINE_STATUSES.index(current_row["status"]) if current_row["status"] in PIPELINE_STATUSES else 0
            new_status = st.selectbox("Pipeline status", PIPELINE_STATUSES, index=current_index)
            if st.button("Update status", use_container_width=True):
                update_status(labels[selected_label], new_status)
                st.success("Pipeline status updated.")
                st.rerun()
        with pipeline_col:
            status_counts = stored["status"].value_counts().reindex(PIPELINE_STATUSES, fill_value=0).reset_index()
            status_counts.columns = ["Status", "Accounts"]
            pipeline_figure = px.funnel(status_counts, y="Status", x="Accounts", color_discrete_sequence=["#0f766e"])
            pipeline_figure.update_layout(height=360, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(pipeline_figure, use_container_width=True)
        st.dataframe(
            stored[["company", "contact_name", "lead_score", "priority_tier", "status", "updated_at"]],
            use_container_width=True,
            hide_index=True,
        )

with method_tab:
    st.subheader("Product and data principles")
    principle_col, architecture_col = st.columns(2)
    with principle_col:
        st.markdown(
            """
            **Transparent prioritization**  
            Each account receives a rule-based score with visible reasons and research gaps.

            **Human approval**  
            Outreach remains a draft. OpsPilot does not send emails or make irreversible CRM changes.

            **Data minimization**  
            The demo contains synthetic contacts. Website research reads only the public homepage supplied by the user.

            **Portable workflow**  
            Leads can enter through CSV or manual entry and leave as an enriched CSV, avoiding vendor lock-in.
            """
        )
    with architecture_col:
        st.markdown(
            """
            **System flow**

            `CSV / form / public webpage`  
            ↓  
            `Normalization and validation`  
            ↓  
            `Explainable ICP scoring`  
            ↓  
            `Human-reviewed outreach draft`  
            ↓  
            `Local SQLite CRM + CSV export`
            """
        )

