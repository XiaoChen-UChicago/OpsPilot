from __future__ import annotations

from datetime import datetime
from io import StringIO
from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import streamlit as st

from opspilot.enrichment import enrich_dataframe
from opspilot.auth import access_token, auth_is_configured, configured_provider, current_user, is_logged_in, render_login
from opspilot.mailer import MailSendError, send_batch
from opspilot.models import LEAD_COLUMNS, canonicalize_leads
from opspilot.outreach import create_outreach_columns, generate_draft
from opspilot.scoring import DEFAULT_INDUSTRIES, ScoringProfile, score_dataframe, score_lead
from opspilot.storage import PIPELINE_STATUSES, load_leads, update_status, upsert_leads


ROOT = Path(__file__).parent
SAMPLE_DATA = ROOT / "data" / "sample_leads.csv"

st.set_page_config(
    page_title="OpsPilot",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

AUTH_ENABLED = auth_is_configured()
AUTH_PROVIDER = configured_provider()
if AUTH_ENABLED and AUTH_PROVIDER and not is_logged_in():
    render_login(AUTH_PROVIDER)
    st.stop()

USER_PROFILE = current_user() if AUTH_ENABLED else {"email": "demo", "name": "Demo workspace", "subject": "demo"}
WORKSPACE_ID = USER_PROFILE["subject"] or USER_PROFILE["email"] or "demo"

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
    section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] { background: #1f2937 !important; background-color: #1f2937 !important; color: #e6edf5 !important; border-color: rgba(230,237,245,.35) !important; }
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


def personalize_template(template: str, row: pd.Series) -> str:
    """Render the small, explainable set of personalization fields used by campaigns."""
    contact_name = str(row.get("contact_name", "")).strip()
    first_name = contact_name.split()[0] if contact_name else "there"
    values = {
        "first_name": first_name,
        "contact_name": contact_name or "there",
        "company": str(row.get("company", "your team")).strip(),
        "title": str(row.get("title", "")).strip() or "your role",
        "industry": str(row.get("industry", "")).strip() or "your industry",
    }
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered


DISCOVERY_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "looking", "find",
    "companies", "company", "teams", "team", "want", "need", "help", "based", "using",
}


def discover_opportunities(goal: str, industries: list[str], countries: list[str], size_range: tuple[int, int]) -> pd.DataFrame:
    """Rank the safe demo catalog against a plain-language opportunity brief."""
    catalog = load_sample()
    if industries:
        catalog = catalog[catalog["industry"].isin(industries)]
    if countries:
        catalog = catalog[catalog["country"].isin(countries)]
    catalog = catalog[
        (catalog["employee_count"] >= size_range[0]) & (catalog["employee_count"] <= size_range[1])
    ].copy()

    terms = [term for term in re.findall(r"[a-zA-Z0-9]+", goal.lower()) if len(term) > 2 and term not in DISCOVERY_STOPWORDS]
    rows: list[dict[str, object]] = []
    for _, row in catalog.iterrows():
        context = " ".join(
            str(row.get(field, "")) for field in ["company", "industry", "title", "description", "country"]
        ).lower()
        matches = [term for term in terms if term in context]
        base_score = score_lead(row, ScoringProfile())
        score = min(100, int(base_score["lead_score"]) + min(25, len(matches) * 6))
        signals = []
        if matches:
            signals.append(f"Goal keywords matched: {', '.join(matches[:4])}")
        signals.append(f"{row['industry']} company with {int(row['employee_count'])} employees")
        if any(word in context for word in ["scal", "manual", "workflow", "ai", "agent"]):
            signals.append("Public description shows an active workflow or scaling signal")
        action = "Research the account" if score < 65 else "Prepare a tailored first conversation"
        rows.append(
            {
                **row.to_dict(),
                "opportunity_score": score,
                "match_reason": " · ".join(signals),
                "recommended_action": action,
            }
        )
    return pd.DataFrame(rows).sort_values(["opportunity_score", "lead_score"], ascending=False).reset_index(drop=True) if rows else pd.DataFrame()


if "leads" not in st.session_state:
    saved_leads = load_leads(WORKSPACE_ID) if AUTH_ENABLED else pd.DataFrame()
    st.session_state.leads = ensure_scored(saved_leads[LEAD_COLUMNS]) if not saved_leads.empty else (
        ensure_scored(load_sample()) if not AUTH_ENABLED else ensure_scored(pd.DataFrame(columns=LEAD_COLUMNS))
    )
if "demo_sends" not in st.session_state:
    st.session_state.demo_sends = []

with st.sidebar:
    st.markdown("### ◈ OpsPilot")
    st.caption("AI-assisted lead research and workflow automation")
    if AUTH_ENABLED:
        st.caption(f"Signed in as {USER_PROFILE['email']}")
        if st.button("Sign out", use_container_width=True):
            st.logout()
    st.markdown("---")
    st.markdown("**Workflow**")
    st.markdown("1. Import leads\n2. Add public context\n3. Score with visible rules\n4. Review outreach drafts\n5. Manage the pipeline")
    st.markdown("---")
    st.info("Demo mode uses synthetic contacts. Drafts are never sent automatically.")
    if st.button("Reset demo data", type="primary", use_container_width=True):
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

discovery_tab, dashboard_tab, intake_tab, research_tab, outreach_tab, crm_tab, method_tab = st.tabs(
    ["Discover Opportunities", "Command Center", "Lead Intake", "Research & Score", "Outreach Studio", "CRM Pipeline", "Methodology"]
)

with discovery_tab:
    st.subheader("Describe your goal")
    st.caption("Start with an objective. OpsPilot will discover and rank the most relevant opportunities before you build a contact list.")
    goal = st.text_area(
        "What are you trying to find?",
        value="Find AI and software companies that are scaling operations and may need workflow automation.",
        height=90,
        key="discovery_goal",
    )
    discovery_col1, discovery_col2, discovery_col3 = st.columns([1.2, 1.2, 1])
    with discovery_col1:
        discovery_industries = st.multiselect(
            "Industries",
            sorted(load_sample()["industry"].unique().tolist()),
            default=["Artificial Intelligence", "Software"],
            key="discovery_industries",
        )
    with discovery_col2:
        discovery_countries = st.multiselect(
            "Countries",
            sorted(load_sample()["country"].unique().tolist()),
            default=["United States"],
            key="discovery_countries",
        )
    with discovery_col3:
        discovery_size = st.slider("Company size", 1, 2000, (10, 500), key="discovery_size")

    if st.button("Discover opportunities", type="primary", use_container_width=True):
        st.session_state.discovery_results = discover_opportunities(
            goal, discovery_industries, discovery_countries, discovery_size
        )

    if "discovery_results" in st.session_state:
        discovered = st.session_state.discovery_results
        if discovered.empty:
            st.warning("No matching opportunities found. Broaden the industry, country, or company-size filters.")
        else:
            high_count = int((discovered["opportunity_score"] >= 75).sum())
            metric_a, metric_b, metric_c = st.columns(3)
            metric_a.metric("Opportunities found", len(discovered))
            metric_b.metric("Strong matches", high_count)
            metric_c.metric("Top opportunity", discovered.iloc[0]["company"])
            st.markdown("#### Opportunity radar")
            st.dataframe(
                discovered[["company", "industry", "country", "opportunity_score", "recommended_action"]],
                use_container_width=True,
                hide_index=True,
                column_config={"opportunity_score": st.column_config.ProgressColumn("Opportunity fit", min_value=0, max_value=100)},
            )
            selected_discovery = st.selectbox("Inspect an opportunity", discovered["company"].tolist(), key="discovery_selected")
            opportunity = discovered[discovered["company"] == selected_discovery].iloc[0]
            detail_col, action_col = st.columns([1.35, 0.85])
            with detail_col:
                st.markdown(f"### {opportunity['company']}")
                st.write(f"**Why it matches:** {opportunity['match_reason']}")
                st.write(f"**Recommended action:** {opportunity['recommended_action']}")
                st.write(f"**Contact:** {opportunity['contact_name']} · {opportunity['title']}")
                st.write(f"**Public context:** {opportunity['description']}")
            with action_col:
                st.markdown("#### Next step")
                st.caption("Move a selected opportunity into the normal research, outreach, and CRM workflow.")
                if st.button("Add to my workspace", type="primary", use_container_width=True, key="add_discovered"):
                    combined = pd.concat([st.session_state.leads[LEAD_COLUMNS], pd.DataFrame([opportunity[LEAD_COLUMNS]])], ignore_index=True)
                    st.session_state.leads = ensure_scored(combined)
                    if AUTH_ENABLED:
                        upsert_leads(st.session_state.leads, WORKSPACE_ID)
                    st.success(f"Added {opportunity['company']} to your workspace.")

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
        if st.session_state.leads.empty:
            st.info("Add an account in Lead Intake before inspecting a score.")
        else:
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
    st.caption("OpsPilot drafts messages for review. Real email is sent only after you approve a specific batch.")
    if st.session_state.leads.empty:
        st.info("Add an account in Lead Intake before preparing outreach.")
    else:
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
            edited_subject = st.text_input("Subject", value=subject, key=f"outreach_subject_{selected_company}")
            edited_body = st.text_area("Message", value=body, height=320, key=f"outreach_body_{selected_company}")
            st.caption("Review the facts, tone, and recipient before using the demo action below.")
            recipient = str(selected.get("email", "")).strip() or "demo.recipient@example.com"
            st.markdown(f"**Demo recipient:** `{recipient}`")
            approved = st.checkbox("I reviewed this draft and recipient", key=f"outreach_approved_{selected_company}")
            if st.button("Simulate send", type="primary", use_container_width=True, disabled=not approved):
                st.session_state.demo_sends.insert(0, {
                    "company": selected_company,
                    "recipient": recipient,
                    "subject": edited_subject,
                    "sent_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "status": "Simulated — not sent",
                })
                st.success("Demo send recorded. No email was sent.")

    if st.session_state.demo_sends:
        st.markdown("#### Demo send history")
        st.dataframe(pd.DataFrame(st.session_state.demo_sends), use_container_width=True, hide_index=True)

    if AUTH_ENABLED:
        st.divider()
        st.markdown("#### Send an approved batch")
        st.caption("Choose up to 20 recipients, edit one campaign template, preview the personalized messages, then approve the send.")
        eligible = st.session_state.leads[st.session_state.leads["email"].str.len() > 0]
        batch_companies = st.multiselect(
            "Recipients",
            eligible["company"].tolist(),
            key="batch_recipients",
            help="Only accounts with a valid email address are listed.",
        )
        batch_subject = ""
        batch_body = ""
        if batch_companies:
            first_batch_row = eligible[eligible["company"] == batch_companies[0]].iloc[0]
            default_subject, default_body = generate_draft(first_batch_row)
            st.markdown("##### Campaign message")
            batch_subject = st.text_input(
                "Subject template",
                value=default_subject,
                key="batch_subject_template",
            )
            batch_body = st.text_area(
                "Message template",
                value=default_body,
                height=260,
                key="batch_body_template",
                help="Use {{first_name}}, {{contact_name}}, {{company}}, {{title}}, and {{industry}} for transparent personalization.",
            )
            st.caption("Available fields: {{first_name}} · {{contact_name}} · {{company}} · {{title}} · {{industry}}")
            preview_rows = []
            for company in batch_companies:
                preview_row = eligible[eligible["company"] == company].iloc[0]
                personalized_body = personalize_template(batch_body, preview_row)
                preview_rows.append(
                    {
                        "company": company,
                        "recipient": str(preview_row["email"]),
                        "subject": personalize_template(batch_subject, preview_row),
                        "opening": personalized_body.splitlines()[0] if personalized_body.splitlines() else "",
                    }
                )
            with st.expander("Preview personalized messages", expanded=True):
                st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
        batch_approved = st.checkbox("I reviewed this recipient list and approve this batch", key="batch_approved")
        if len(batch_companies) > 20:
            st.error("A single send action is limited to 20 recipients.")
        if st.button(
            "Send approved batch",
            type="primary",
            use_container_width=True,
            disabled=not batch_companies or not batch_approved or len(batch_companies) > 20,
        ):
            token = access_token()
            if not token:
                st.error("Mailbox connection is not configured for sending. Ask the workspace administrator to enable access tokens.")
            else:
                messages = []
                for company in batch_companies:
                    row = eligible[eligible["company"] == company].iloc[0]
                    messages.append(
                        {
                            "recipient": str(row["email"]),
                            "subject": personalize_template(batch_subject, row),
                            "body": personalize_template(batch_body, row),
                        }
                    )
                try:
                    sent_count = send_batch(AUTH_PROVIDER or "", token, messages, max_messages=20)
                    st.success(f"Sent {sent_count} approved message(s) from the connected mailbox.")
                except MailSendError as error:
                    st.error(f"The batch was not completed: {error}")
    else:
        st.info("Workspace mode is off in the public demo. Sign-in and real batch sending appear after an OIDC provider is configured.")

with crm_tab:
    st.subheader("Manage a lightweight local pipeline")
    save_col, export_col = st.columns([1, 1])
    with save_col:
        if st.button("Save current accounts to CRM", type="primary", use_container_width=True):
            saved = upsert_leads(st.session_state.leads, WORKSPACE_ID)
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

    stored = load_leads(WORKSPACE_ID)
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
                update_status(labels[selected_label], new_status, WORKSPACE_ID)
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

