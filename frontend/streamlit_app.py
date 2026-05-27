import html
import os
from urllib.parse import urlparse

import requests
import streamlit as st
from dotenv import load_dotenv


load_dotenv()

BACKEND_API_URL = os.getenv(
    "BACKEND_API_URL",
    "http://127.0.0.1:8000"
)

APP_API_KEY = os.getenv(
    "APP_API_KEY",
    ""
)

EXAMPLE_QUERIES = [
    "What is ROE?",
    "Current price of HDFC Bank",
    "Compare HDFC Bank vs ICICI Bank",
    "Top undervalued IT stocks in India",
    "Latest news about Infosys",
    "Fundamental analysis of TCS"
]


def escape_html(value):

    if isinstance(value, str):

        return html.escape(
            value,
            quote=True
        )

    if isinstance(value, list):

        return [
            escape_html(item)
            for item in value
        ]

    if isinstance(value, dict):

        return {
            key: escape_html(item)
            for key, item in value.items()
        }

    return value


def confidence_label(score):

    if score >= 0.85:

        return "Very high"

    if score >= 0.70:

        return "High"

    if score >= 0.50:

        return "Medium"

    return "Low"


def render_html(markup):

    st.markdown(
        markup,
        unsafe_allow_html=True
    )


def render_badge(text, tone="blue"):

    render_html(
        f"<span class='badge badge-{tone}'>{text}</span>"
    )


def render_panel(title, body, tone="neutral"):

    if not body:

        return

    render_html(
        f"""
        <section class="panel panel-{tone}">
            <div class="panel-title">{title}</div>
            <div class="panel-body">{body}</div>
        </section>
        """
    )


def render_list(title, items, tone="blue", prefix=None):

    if not items:

        return

    st.markdown(
        f"### {title}"
    )

    for item in items:

        label = (
            f"{prefix}: {item}"
            if prefix
            else item
        )

        render_html(
            f"<div class='list-item list-{tone}'>{label}</div>"
        )


def source_label(url):

    parsed = urlparse(url)

    return (
        parsed.netloc.replace("www.", "")
        or url
    )


def render_sources(title, sources):

    if not sources:

        return

    st.markdown(
        f"### {title}"
    )

    for source in sources:

        render_html(
            f"""
            <a class="source-link" href="{source}" target="_blank">
                {source_label(source)}
            </a>
            """
        )


def render_metric_card(label, value):

    if value in [None, "", "N/A"]:

        return

    render_html(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """
    )


def fetch_analysis(query):

    response = requests.post(
        f"{BACKEND_API_URL}/chat",
        json={
            "query": query
        },
        headers={
            "X-API-Key": APP_API_KEY
        },
        timeout=60
    )

    response.raise_for_status()

    return response.json()


def render_header():

    render_html(
        """
        <div class="app-hero">
            <div>
                <div class="eyebrow">Indian Market Intelligence</div>
                <h1>FinIntel AI</h1>
                <p>
                    Ask for prices, fundamentals, comparisons, news,
                    or plain-English financial explanations.
                </p>
            </div>
        </div>
        """
    )


def render_summary(data, route, routing, payload):

    title = (
        payload.get("company_name")
        or payload.get("comparison_type")
        or payload.get("topic")
        or payload.get("query_type")
        or "FinIntel Analysis"
    )

    ticker = payload.get("ticker", "")
    score = float(
        payload.get(
            "confidence_score",
            0
        )
        or 0
    )
    percent = int(score * 100)
    reasoning = routing.get(
        "reasoning",
        ""
    )

    render_html(
        f"""
        <div class="summary-grid">
            <section class="summary-card">
                <div class="summary-topline">
                    <span class="badge badge-blue">{route}</span>
                    <span class="badge badge-muted">{data.get("query", "")}</span>
                </div>
                <h2>{title}</h2>
                <div class="ticker">{ticker}</div>
                <div class="reasoning">{reasoning}</div>
            </section>
            <section class="confidence-card">
                <div class="metric-label">Confidence</div>
                <div class="confidence-score">{percent}%</div>
                <div class="confidence-label">{confidence_label(score)}</div>
            </section>
        </div>
        """
    )

    st.progress(score)


def render_price(payload):

    render_panel(
        "Current Trading Information",
        payload.get("message")
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        current_price = payload.get(
            "current_price"
        )

        render_metric_card(
            "Current Price",
            (
                f"INR {current_price}"
                if current_price is not None
                else None
            )
        )

    with col2:

        render_metric_card(
            "P/E Ratio",
            payload.get("pe_ratio")
        )

    with col3:

        render_metric_card(
            "Market Cap",
            payload.get("market_cap")
        )

    with col4:

        render_metric_card(
            "Sector",
            payload.get("sector")
        )


def render_educational(payload):

    render_panel(
        "Simple Definition",
        payload.get("simple_definition")
    )
    render_panel(
        "Detailed Explanation",
        payload.get("detailed_explanation")
    )
    render_panel(
        "Why It Matters",
        payload.get("why_it_matters"),
        tone="green"
    )
    render_panel(
        "Practical Interpretation",
        payload.get("practical_interpretation"),
        tone="blue"
    )
    render_panel(
        "Limitations",
        payload.get("limitations"),
        tone="red"
    )
    render_panel(
        "Example",
        payload.get("example"),
        tone="blue"
    )
    render_sources(
        "Sources",
        payload.get("sources_used")
    )


def render_discovery(payload):

    render_panel(
        "Market Overview",
        payload.get("summary")
    )
    render_list(
        "Key Points",
        payload.get("key_points"),
        tone="blue"
    )
    render_list(
        "Companies To Explore",
        payload.get("mentioned_companies"),
        tone="blue",
        prefix="Company"
    )
    render_sources(
        "Sources",
        payload.get("sources_used")
    )


def render_news(payload):

    render_panel(
        "Headline Summary",
        payload.get("headline_summary")
    )
    render_list(
        "Key Events",
        payload.get("key_events"),
        tone="blue",
        prefix="Event"
    )
    render_panel(
        "Market Impact",
        payload.get("market_impact"),
        tone="blue"
    )
    render_list(
        "Risk Factors",
        payload.get("risk_factors"),
        tone="red",
        prefix="Risk"
    )
    render_sources(
        "Sources",
        payload.get("sources")
    )


def render_comparison(payload):

    render_panel(
        "Summary",
        payload.get("summary")
    )
    render_list(
        "Comparative Analysis",
        payload.get("comparative_analysis"),
        tone="blue",
        prefix="Analysis"
    )
    render_panel(
        "Winner Summary",
        payload.get("winner_summary"),
        tone="green"
    )
    render_panel(
        "Balanced View",
        payload.get("balanced_view")
    )
    render_sources(
        "Sources",
        payload.get("sources_used")
    )


def render_fundamental(payload):

    render_panel(
        "Business Overview",
        payload.get("business_overview")
    )
    render_list(
        "Strengths",
        payload.get("financial_strengths"),
        tone="green",
        prefix="Strength"
    )
    render_list(
        "Risks",
        payload.get("financial_risks"),
        tone="red",
        prefix="Risk"
    )
    render_panel(
        "Valuation Commentary",
        payload.get("valuation_commentary"),
        tone="blue"
    )
    render_panel(
        "Overall View",
        payload.get("overall_view")
    )
    render_sources(
        "Sources",
        payload.get("sources_used")
    )


def render_route_payload(route, payload):

    if route == "PRICE_QUERY":

        render_price(payload)

    elif route == "EDUCATIONAL":

        render_educational(payload)

    elif route == "DISCOVERY":

        render_discovery(payload)

    elif route == "NEWS":

        render_news(payload)

    elif route == "COMPARISON":

        render_comparison(payload)

    elif route == "FUNDAMENTAL":

        render_fundamental(payload)


st.set_page_config(
    page_title="FinIntel AI",
    page_icon="FI",
    layout="wide"
)

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        background: #f8fafc;
        color: #0f172a;
        font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 4rem;
    }

    .app-hero {
        background: linear-gradient(135deg, #0f172a 0%, #172554 58%, #1e3a8a 100%);
        border-radius: 8px;
        color: white;
        padding: 34px;
        margin-bottom: 22px;
        border: 1px solid rgba(255,255,255,0.12);
    }

    .app-hero h1 {
        font-size: 42px;
        margin: 4px 0 8px 0;
        line-height: 1;
    }

    .app-hero p {
        color: #cbd5e1;
        font-size: 17px;
        max-width: 720px;
        margin: 0;
    }

    .eyebrow {
        color: #bfdbfe;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .stTextInput input {
        background: white !important;
        color: #0f172a !important;
        border-radius: 8px !important;
        border: 1px solid #cbd5e1 !important;
        height: 48px;
        font-size: 16px;
    }

    .stButton button {
        background: #1d4ed8;
        color: white;
        border: 0;
        border-radius: 8px;
        min-height: 48px;
        font-weight: 700;
    }

    .summary-grid {
        display: grid;
        grid-template-columns: minmax(0, 1fr) 220px;
        gap: 16px;
        margin: 22px 0 12px 0;
    }

    .summary-card,
    .confidence-card,
    .metric-card,
    .panel {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    }

    .summary-card {
        padding: 24px;
    }

    .summary-card h2 {
        color: #0f172a;
        font-size: 32px;
        margin: 12px 0 6px 0;
        line-height: 1.15;
    }

    .summary-topline {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
    }

    .ticker,
    .reasoning,
    .confidence-label,
    .metric-label {
        color: #64748b;
    }

    .ticker {
        font-size: 15px;
        font-weight: 700;
    }

    .reasoning {
        margin-top: 14px;
        font-size: 14px;
        line-height: 1.5;
    }

    .confidence-card {
        padding: 24px;
        text-align: center;
    }

    .confidence-score {
        color: #0f172a;
        font-size: 44px;
        font-weight: 900;
        margin: 8px 0;
    }

    .metric-card {
        min-height: 116px;
        padding: 18px;
        margin-bottom: 14px;
    }

    .metric-value {
        color: #0f172a;
        font-size: 24px;
        font-weight: 800;
        margin-top: 10px;
        overflow-wrap: anywhere;
    }

    .badge {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 800;
        padding: 6px 10px;
    }

    .badge-blue {
        background: #dbeafe;
        color: #1d4ed8;
    }

    .badge-muted {
        background: #f1f5f9;
        color: #475569;
        max-width: 100%;
        overflow-wrap: anywhere;
    }

    .panel {
        padding: 20px;
        margin: 14px 0;
    }

    .panel-blue,
    .list-blue {
        border-left: 4px solid #2563eb;
    }

    .panel-green,
    .list-green {
        border-left: 4px solid #16a34a;
    }

    .panel-red,
    .list-red {
        border-left: 4px solid #dc2626;
    }

    .panel-title {
        color: #0f172a;
        font-size: 16px;
        font-weight: 800;
        margin-bottom: 8px;
    }

    .panel-body {
        color: #334155;
        font-size: 16px;
        line-height: 1.7;
    }

    .list-item {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 10px;
        color: #334155;
        line-height: 1.6;
    }

    .source-link {
        display: block;
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 8px;
        color: #1d4ed8 !important;
        text-decoration: none;
        font-weight: 700;
    }

    .footer-note {
        color: #64748b;
        font-size: 13px;
        line-height: 1.6;
        margin-top: 26px;
        border-top: 1px solid #e2e8f0;
        padding-top: 18px;
    }

    @media (max-width: 760px) {
        .summary-grid {
            grid-template-columns: 1fr;
        }

        .app-hero {
            padding: 24px;
        }

        .app-hero h1 {
            font-size: 34px;
        }

        .summary-card h2 {
            font-size: 26px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True
)

render_header()

with st.form("query-form"):

    query = st.text_input(
        "Ask a financial question",
        placeholder="Compare HDFC Bank vs ICICI Bank"
    )

    submitted = st.form_submit_button(
        "Analyze"
    )

st.caption(
    "Examples: "
    + " | ".join(EXAMPLE_QUERIES)
)

if submitted:

    if not query.strip():

        st.warning(
            "Enter a question to analyze."
        )

        st.stop()

    with st.spinner("Analyzing market context..."):

        try:

            raw_data = fetch_analysis(
                query.strip()
            )

        except requests.RequestException as e:

            st.error(
                f"Backend request failed: {e}"
            )

            st.stop()

        except ValueError:

            st.error(
                "Backend returned an invalid JSON response."
            )

            st.stop()

    data = escape_html(raw_data)
    result = data.get("response", {})
    route = data.get("route", "UNKNOWN")
    routing = data.get("routing", {})

    if not result.get("success"):

        st.error(
            result.get(
                "error",
                "Unknown error"
            )
        )

        with st.expander("Debug details"):

            st.json(data)

        st.stop()

    payload = result.get(
        "data",
        {}
    )

    render_summary(
        data=data,
        route=route,
        routing=routing,
        payload=payload
    )

    render_route_payload(
        route,
        payload
    )

    if payload.get("disclaimer"):

        render_html(
            f"""
            <div class="footer-note">
                <strong>Disclaimer:</strong> {payload["disclaimer"]}
            </div>
            """
        )

    with st.expander("Routing and confidence details"):

        st.json(
            {
                "route": route,
                "routing": routing,
                "query_intelligence": data.get(
                    "query_intelligence"
                ),
                "confidence_breakdown": payload.get(
                    "confidence_breakdown"
                )
            }
        )
