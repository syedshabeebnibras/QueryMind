"""QueryMind — Premium NL-to-SQL interface with landing + workspace views."""

import asyncio
import uuid

import pandas as pd
import streamlit as st

# ──────────────────────────────────────────────────────────────
# Session bootstrap
# ──────────────────────────────────────────────────────────────
_user_param = st.query_params.get("user")
if _user_param:
    st.session_state["user_id"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, _user_param))
elif "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())

# View mode: "landing" or "workspace"
_view_param = st.query_params.get("view")
if _view_param in ("landing", "workspace"):
    st.session_state["view_mode"] = _view_param
elif "view_mode" not in st.session_state:
    st.session_state["view_mode"] = "landing"

from api_client import (
    create_connection,
    delete_connection,
    get_connections,
    get_history,
    get_tables,
    health_check,
    import_table,
    run_query,
    setup_schema,
    submit_feedback,
    BACKEND_URL,
)

st.set_page_config(page_title="QueryMind", page_icon="Q", layout="wide")


# ──────────────────────────────────────────────────────────────
# Design tokens (CSS custom properties)
# ──────────────────────────────────────────────────────────────
_DESIGN_TOKENS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    :root {
        --qm-bg-deep:      #0a0a0c;
        --qm-bg-base:      #121214;
        --qm-bg-raised:    #1a1a1d;
        --qm-bg-surface:   #1f1f23;
        --qm-bg-hover:     #26262b;
        --qm-border:       rgba(228, 228, 231, 0.06);
        --qm-border-hover: rgba(228, 228, 231, 0.12);
        --qm-border-focus: rgba(138, 143, 152, 0.3);
        --qm-text-primary: #e4e4e7;
        --qm-text-secondary: rgba(228, 228, 231, 0.55);
        --qm-text-tertiary: rgba(228, 228, 231, 0.3);
        --qm-text-ghost:   rgba(228, 228, 231, 0.18);
        --qm-accent:       #8a8f98;
        --qm-accent-glow:  rgba(138, 143, 152, 0.08);
        --qm-green:        rgba(74, 222, 128, 0.7);
        --qm-green-bg:     rgba(74, 222, 128, 0.06);
        --qm-red:          rgba(248, 113, 113, 0.7);
        --qm-red-bg:       rgba(248, 113, 113, 0.06);
        --qm-radius-sm:    8px;
        --qm-radius-md:    12px;
        --qm-radius-lg:    16px;
        --qm-radius-xl:    20px;
        --qm-font:         'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', system-ui, sans-serif;
        --qm-spring:       cubic-bezier(0.16, 1, 0.3, 1);
        --qm-ease:         cubic-bezier(0.4, 0, 0.2, 1);
    }

    /* ── Reset ── */
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        font-family: var(--qm-font);
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    [data-testid="stAppViewContainer"] {
        background: var(--qm-bg-deep);
    }
    [data-testid="stApp"] {
        background: var(--qm-bg-deep);
    }

    /* ── Animations ── */
    @keyframes fadeSlideUp {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    @keyframes shimmer {
        0%   { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    @keyframes pulseGlow {
        0%, 100% { box-shadow: 0 0 15px rgba(138, 143, 152, 0.04); }
        50%      { box-shadow: 0 0 25px rgba(138, 143, 152, 0.08); }
    }

    /* ── Landing page ── */
    .qm-landing-nav {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1.25rem 3rem;
        position: sticky;
        top: 0;
        z-index: 100;
        background: rgba(10, 10, 12, 0.75);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-bottom: 0.5px solid var(--qm-border);
        animation: fadeIn 0.4s var(--qm-spring) both;
    }
    .qm-landing-nav .brand {
        display: flex;
        align-items: center;
        gap: 10px;
        text-decoration: none;
    }
    .qm-landing-nav .brand-icon {
        width: 32px; height: 32px;
        border-radius: 8px;
        background: linear-gradient(135deg, var(--qm-bg-surface) 0%, var(--qm-bg-raised) 100%);
        border: 0.5px solid var(--qm-border);
        display: flex; align-items: center; justify-content: center;
        font-size: 0.85rem; font-weight: 700; color: var(--qm-accent);
        box-shadow: 0 1px 3px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.03);
    }
    .qm-landing-nav .brand-text {
        font-size: 1rem; font-weight: 600;
        color: var(--qm-text-primary);
        letter-spacing: -0.3px;
    }
    .qm-landing-nav .nav-links {
        display: flex; gap: 2rem; align-items: center;
    }
    .qm-landing-nav .nav-links a {
        font-size: 0.8rem; font-weight: 450;
        color: var(--qm-text-secondary);
        text-decoration: none;
        letter-spacing: 0.2px;
        transition: color 0.2s var(--qm-ease);
    }
    .qm-landing-nav .nav-links a:hover {
        color: var(--qm-text-primary);
    }

    .qm-landing-hero {
        text-align: center;
        padding: 6rem 2rem 4rem 2rem;
        max-width: 720px;
        margin: 0 auto;
        animation: fadeSlideUp 0.6s 0.1s var(--qm-spring) both;
    }
    .qm-landing-hero .badge {
        display: inline-block;
        font-size: 0.68rem; font-weight: 500;
        letter-spacing: 1px; text-transform: uppercase;
        color: var(--qm-accent);
        background: var(--qm-accent-glow);
        border: 0.5px solid rgba(138, 143, 152, 0.12);
        padding: 5px 14px;
        border-radius: 20px;
        margin-bottom: 1.75rem;
    }
    .qm-landing-hero h1 {
        font-size: 3.2rem; font-weight: 800;
        letter-spacing: -1.8px; line-height: 1.08;
        color: var(--qm-text-primary);
        margin: 0 0 1.25rem 0;
    }
    .qm-landing-hero h1 .gradient-text {
        background: linear-gradient(135deg, #e4e4e7 0%, #8a8f98 50%, #5a5d63 100%);
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: shimmer 6s linear infinite;
    }
    .qm-landing-hero p {
        font-size: 1.05rem; font-weight: 400;
        color: var(--qm-text-secondary);
        line-height: 1.65;
        margin: 0 auto 2.5rem auto;
        max-width: 520px;
    }

    /* ── CTA button (HTML) ── */
    .qm-cta-wrap {
        display: flex;
        justify-content: center;
        gap: 0.75rem;
        animation: fadeSlideUp 0.6s 0.3s var(--qm-spring) both;
    }

    /* ── Feature cards ── */
    .qm-features {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1.25rem;
        max-width: 900px;
        margin: 0 auto;
        padding: 0 2rem 4rem 2rem;
    }
    .qm-feature-card {
        background: linear-gradient(180deg, var(--qm-bg-raised) 0%, rgba(26,26,29,0.5) 100%);
        border: 0.5px solid var(--qm-border);
        border-radius: var(--qm-radius-lg);
        padding: 1.75rem 1.5rem;
        transition: all 0.3s var(--qm-spring);
        animation: fadeSlideUp 0.5s var(--qm-spring) both;
    }
    .qm-feature-card:nth-child(1) { animation-delay: 0.15s; }
    .qm-feature-card:nth-child(2) { animation-delay: 0.25s; }
    .qm-feature-card:nth-child(3) { animation-delay: 0.35s; }
    .qm-feature-card:nth-child(4) { animation-delay: 0.45s; }
    .qm-feature-card:nth-child(5) { animation-delay: 0.55s; }
    .qm-feature-card:nth-child(6) { animation-delay: 0.65s; }
    .qm-feature-card:hover {
        border-color: var(--qm-border-hover);
        transform: translateY(-2px) scale(1.01);
        box-shadow: 0 8px 32px rgba(0,0,0,0.2), 0 0 0 1px rgba(138,143,152,0.04);
    }
    .qm-feature-card .icon {
        width: 36px; height: 36px;
        border-radius: 10px;
        background: var(--qm-bg-surface);
        border: 0.5px solid var(--qm-border);
        display: flex; align-items: center; justify-content: center;
        font-size: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.2);
    }
    .qm-feature-card h3 {
        font-size: 0.88rem; font-weight: 600;
        color: var(--qm-text-primary);
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.2px;
    }
    .qm-feature-card p {
        font-size: 0.8rem; font-weight: 400;
        color: var(--qm-text-secondary);
        line-height: 1.55;
        margin: 0;
    }

    /* ── Section headings ── */
    .qm-section-heading {
        text-align: center;
        padding: 3rem 2rem 2rem 2rem;
        animation: fadeSlideUp 0.5s var(--qm-spring) both;
    }
    .qm-section-heading h2 {
        font-size: 1.6rem; font-weight: 700;
        letter-spacing: -0.8px;
        color: var(--qm-text-primary);
        margin: 0 0 0.5rem 0;
    }
    .qm-section-heading p {
        font-size: 0.88rem;
        color: var(--qm-text-tertiary);
        margin: 0;
    }

    /* ── Tech stack pills ── */
    .qm-tech-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
        justify-content: center;
        max-width: 700px;
        margin: 0 auto;
        padding: 0 2rem 4rem 2rem;
        animation: fadeSlideUp 0.5s 0.2s var(--qm-spring) both;
    }
    .qm-tech-pill {
        font-size: 0.75rem; font-weight: 500;
        color: var(--qm-text-secondary);
        background: var(--qm-bg-raised);
        border: 0.5px solid var(--qm-border);
        padding: 6px 14px;
        border-radius: 20px;
        transition: all 0.2s var(--qm-ease);
        letter-spacing: 0.2px;
    }
    .qm-tech-pill:hover {
        border-color: var(--qm-border-hover);
        color: var(--qm-text-primary);
        background: var(--qm-bg-hover);
    }

    /* ── Security section ── */
    .qm-security-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
        max-width: 700px;
        margin: 0 auto;
        padding: 0 2rem 4rem 2rem;
        animation: fadeSlideUp 0.5s 0.2s var(--qm-spring) both;
    }
    .qm-security-item {
        display: flex; gap: 0.75rem; align-items: flex-start;
        padding: 1rem 1.25rem;
        background: var(--qm-bg-raised);
        border: 0.5px solid var(--qm-border);
        border-radius: var(--qm-radius-md);
        transition: all 0.25s var(--qm-spring);
    }
    .qm-security-item:hover {
        border-color: var(--qm-border-hover);
        transform: translateY(-1px);
    }
    .qm-security-item .dot {
        width: 6px; height: 6px;
        border-radius: 50%;
        background: var(--qm-accent);
        margin-top: 6px;
        flex-shrink: 0;
        box-shadow: 0 0 6px rgba(138, 143, 152, 0.3);
    }
    .qm-security-item .text h4 {
        font-size: 0.82rem; font-weight: 600;
        color: var(--qm-text-primary);
        margin: 0 0 0.25rem 0;
        letter-spacing: -0.1px;
    }
    .qm-security-item .text p {
        font-size: 0.75rem;
        color: var(--qm-text-tertiary);
        margin: 0; line-height: 1.5;
    }

    /* ── Footer ── */
    .qm-footer {
        text-align: center;
        padding: 3rem 2rem;
        border-top: 0.5px solid var(--qm-border);
        animation: fadeIn 0.5s 0.4s var(--qm-spring) both;
    }
    .qm-footer p {
        font-size: 0.75rem;
        color: var(--qm-text-ghost);
        margin: 0;
        letter-spacing: 0.2px;
    }
    .qm-footer a {
        color: var(--qm-text-tertiary);
        text-decoration: none;
        transition: color 0.2s ease;
    }
    .qm-footer a:hover { color: var(--qm-text-secondary); }

    /* ── Workspace layout ── */
    .qm-workspace-container .block-container {
        max-width: 780px;
        padding-top: 2rem;
    }
    .qm-ws-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 0 1.5rem 0;
        animation: fadeSlideUp 0.4s var(--qm-spring) both;
    }
    .qm-ws-header .brand {
        display: flex; align-items: center; gap: 10px;
    }
    .qm-ws-header .brand-icon {
        width: 30px; height: 30px;
        border-radius: 8px;
        background: linear-gradient(135deg, var(--qm-bg-surface) 0%, var(--qm-bg-raised) 100%);
        border: 0.5px solid var(--qm-border);
        display: flex; align-items: center; justify-content: center;
        font-size: 0.78rem; font-weight: 700; color: var(--qm-accent);
    }
    .qm-ws-header .brand-text {
        font-size: 0.9rem; font-weight: 600;
        color: var(--qm-text-primary);
        letter-spacing: -0.3px;
    }
    .qm-ws-header .back-link {
        font-size: 0.75rem; font-weight: 450;
        color: var(--qm-text-tertiary);
        letter-spacing: 0.2px;
        cursor: pointer;
        transition: color 0.2s ease;
    }
    .qm-ws-header .back-link:hover {
        color: var(--qm-text-secondary);
    }

    /* ── Workspace inputs ── */
    .stTextArea textarea,
    .stTextInput input {
        background: var(--qm-bg-raised) !important;
        border: 0.5px solid var(--qm-border) !important;
        border-radius: var(--qm-radius-sm) !important;
        color: var(--qm-text-primary) !important;
        font-family: var(--qm-font) !important;
        font-size: 0.88rem !important;
        padding: 0.85rem 1rem !important;
        transition: border-color 0.25s var(--qm-spring),
                    box-shadow 0.25s var(--qm-spring) !important;
        caret-color: var(--qm-accent) !important;
    }
    .stTextArea textarea:focus,
    .stTextInput input:focus {
        border-color: var(--qm-border-focus) !important;
        box-shadow: 0 0 0 3px rgba(138, 143, 152, 0.06),
                    0 1px 2px rgba(0,0,0,0.2) !important;
        outline: none !important;
    }
    .stTextArea textarea::placeholder,
    .stTextInput input::placeholder {
        color: var(--qm-text-ghost) !important;
        font-weight: 400 !important;
    }

    /* ── Primary button ── */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(180deg, #2a2a2e 0%, #212124 100%) !important;
        border: 0.5px solid rgba(228, 228, 231, 0.1) !important;
        border-radius: var(--qm-radius-sm) !important;
        color: var(--qm-text-primary) !important;
        font-family: var(--qm-font) !important;
        font-weight: 500 !important;
        font-size: 0.86rem !important;
        letter-spacing: 0.1px !important;
        padding: 0.65rem 1.5rem !important;
        transition: all 0.2s var(--qm-spring) !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.25),
                    inset 0 1px 0 rgba(255,255,255,0.04) !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(180deg, #303034 0%, #28282c 100%) !important;
        border-color: rgba(228, 228, 231, 0.15) !important;
        box-shadow: 0 3px 12px rgba(0,0,0,0.3),
                    inset 0 1px 0 rgba(255,255,255,0.05) !important;
        transform: translateY(-0.5px) !important;
    }
    .stButton > button[kind="primary"]:active,
    .stButton > button[data-testid="stBaseButton-primary"]:active {
        transform: scale(0.975) translateY(0) !important;
        box-shadow: 0 0 0 rgba(0,0,0,0.15) !important;
    }

    /* ── Secondary buttons ── */
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="stBaseButton-secondary"],
    .stButton > button:not([kind]) {
        background: transparent !important;
        border: 0.5px solid var(--qm-border) !important;
        border-radius: var(--qm-radius-sm) !important;
        color: var(--qm-text-secondary) !important;
        font-family: var(--qm-font) !important;
        font-weight: 500 !important;
        font-size: 0.8rem !important;
        padding: 0.5rem 1.25rem !important;
        transition: all 0.2s var(--qm-spring) !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="stBaseButton-secondary"]:hover,
    .stButton > button:not([kind]):hover {
        background: rgba(228, 228, 231, 0.03) !important;
        border-color: var(--qm-border-hover) !important;
        color: var(--qm-text-primary) !important;
    }
    .stButton > button[kind="secondary"]:active,
    .stButton > button[data-testid="stBaseButton-secondary"]:active,
    .stButton > button:not([kind]):active {
        transform: scale(0.97) !important;
    }

    /* ── Expander ── */
    .streamlit-expanderHeader {
        background: rgba(26, 26, 29, 0.6) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 0.5px solid var(--qm-border) !important;
        border-radius: var(--qm-radius-sm) !important;
        font-family: var(--qm-font) !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        color: var(--qm-text-secondary) !important;
        letter-spacing: 0.2px !important;
        padding: 0.7rem 1rem !important;
        transition: all 0.25s var(--qm-spring) !important;
    }
    .streamlit-expanderHeader:hover {
        border-color: var(--qm-border-hover) !important;
        color: var(--qm-text-primary) !important;
    }
    [data-testid="stExpander"] {
        border: 0.5px solid rgba(228, 228, 231, 0.03) !important;
        border-radius: var(--qm-radius-sm) !important;
        overflow: hidden;
    }
    [data-testid="stExpander"] details {
        border: none !important;
    }

    /* ── Code blocks ── */
    .stCodeBlock, pre, code { border-radius: var(--qm-radius-sm) !important; }
    [data-testid="stCodeBlock"] {
        border: 0.5px solid rgba(228, 228, 231, 0.04) !important;
        border-radius: var(--qm-radius-sm) !important;
        overflow: hidden;
    }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] {
        border: 0.5px solid var(--qm-border) !important;
        border-radius: var(--qm-radius-md) !important;
        overflow: hidden;
        animation: fadeSlideUp 0.4s var(--qm-spring) both;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: rgba(14, 14, 16, 0.85) !important;
        backdrop-filter: blur(24px) !important;
        -webkit-backdrop-filter: blur(24px) !important;
        border-right: 0.5px solid var(--qm-border) !important;
    }

    /* ── Status pill ── */
    .qm-status-pill {
        display: inline-flex; align-items: center; gap: 6px;
        font-family: var(--qm-font);
        font-size: 0.7rem; font-weight: 500;
        letter-spacing: 0.5px; text-transform: uppercase;
        padding: 5px 12px; border-radius: 20px;
    }
    .qm-status-pill.online {
        background: var(--qm-green-bg);
        color: var(--qm-green);
        border: 0.5px solid rgba(74, 222, 128, 0.1);
    }
    .qm-status-pill.offline {
        background: var(--qm-red-bg);
        color: var(--qm-red);
        border: 0.5px solid rgba(248, 113, 113, 0.1);
    }

    /* ── Sidebar labels ── */
    .qm-section-label {
        font-family: var(--qm-font);
        font-size: 0.62rem; font-weight: 600;
        letter-spacing: 1.5px; text-transform: uppercase;
        color: var(--qm-text-tertiary);
        margin: 1rem 0 0.5rem 0;
    }
    .qm-table-item {
        font-family: var(--qm-font); font-size: 0.8rem;
        color: var(--qm-text-secondary); padding: 3px 0;
    }
    .qm-table-item code {
        font-size: 0.76rem;
        color: rgba(228, 228, 231, 0.65);
        background: rgba(228, 228, 231, 0.04);
        padding: 2px 6px; border-radius: 4px;
        border: 0.5px solid var(--qm-border);
    }
    .qm-table-item .cols {
        color: var(--qm-text-tertiary);
        font-size: 0.7rem; margin-left: 4px;
    }

    /* ── Result labels ── */
    .qm-label {
        font-family: var(--qm-font);
        font-size: 0.62rem; font-weight: 600;
        letter-spacing: 1.5px; text-transform: uppercase;
        color: var(--qm-text-tertiary);
        margin-bottom: 0.5rem;
    }

    /* ── Metrics strip ── */
    .qm-metrics-strip {
        display: flex; gap: 1.25rem; padding: 0.5rem 0;
        font-family: var(--qm-font);
        font-size: 0.76rem;
        color: var(--qm-text-tertiary);
        animation: fadeIn 0.5s 0.2s both;
    }
    .qm-metrics-strip .val {
        color: var(--qm-text-secondary);
        font-weight: 500;
    }

    /* ── User badge ── */
    .qm-user-badge {
        font-family: var(--qm-font);
        font-size: 0.7rem; font-weight: 500;
        color: var(--qm-text-tertiary);
        padding: 2px 0; letter-spacing: 0.2px;
    }

    /* ── Selectbox ── */
    [data-testid="stSelectbox"] > div > div {
        background: var(--qm-bg-raised) !important;
        border: 0.5px solid var(--qm-border) !important;
        border-radius: var(--qm-radius-sm) !important;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        border: 0.5px dashed var(--qm-border) !important;
        border-radius: var(--qm-radius-sm) !important;
        transition: border-color 0.25s ease !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: var(--qm-border-hover) !important;
    }

    /* ── Alerts, progress, toast ── */
    [data-testid="stAlert"] {
        border-radius: var(--qm-radius-sm) !important;
        border-width: 0.5px !important;
        font-size: 0.84rem !important;
    }
    .stProgress > div > div {
        background: rgba(138, 143, 152, 0.12) !important;
        border-radius: 4px !important;
    }
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #8a8f98, #6b6f77) !important;
        border-radius: 4px !important;
    }
    [data-testid="stToast"] {
        backdrop-filter: blur(12px) !important;
        border: 0.5px solid var(--qm-border) !important;
        border-radius: var(--qm-radius-sm) !important;
    }
    [data-testid="stVegaLiteChart"] {
        border: 0.5px solid rgba(228, 228, 231, 0.03) !important;
        border-radius: var(--qm-radius-sm) !important;
        overflow: hidden; padding: 0.5rem;
    }
    .stCaption, [data-testid="stCaption"] {
        font-family: var(--qm-font) !important;
    }

    /* ── Subtle dividers ── */
    hr {
        border: none;
        border-top: 0.5px solid var(--qm-border);
        margin: 1.5rem 0;
    }

    /* ── Responsive ── */
    @media (max-width: 768px) {
        .qm-landing-hero h1 { font-size: 2.2rem; letter-spacing: -1px; }
        .qm-features { grid-template-columns: 1fr; }
        .qm-security-grid { grid-template-columns: 1fr; }
        .qm-landing-nav { padding: 1rem 1.5rem; }
        .qm-landing-nav .nav-links { gap: 1rem; }
        .qm-landing-nav .nav-links a { font-size: 0.72rem; }
    }
</style>
"""

st.markdown(_DESIGN_TOKENS, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# VIEW: LANDING
# ══════════════════════════════════════════════════════════════
def _render_landing():
    """Render the marketing-style landing page."""

    # ── Nav ──
    st.markdown("""
    <div class="qm-landing-nav">
        <div class="brand">
            <div class="brand-icon">Q</div>
            <span class="brand-text">QueryMind</span>
        </div>
        <div class="nav-links">
            <a href="#features">Features</a>
            <a href="#tech-stack">Tech Stack</a>
            <a href="#security">Security</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Hero ──
    st.markdown("""
    <div class="qm-landing-hero">
        <div class="badge">Natural Language to SQL</div>
        <h1>Ask your data anything.<br/><span class="gradient-text">Get answers instantly.</span></h1>
        <p>
            QueryMind translates plain English into safe, validated SQL queries.
            Built with a self-correcting AI pipeline, enterprise-grade security,
            and an adaptive learning loop that improves with every interaction.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── CTA ──
    _, cta_col, _ = st.columns([2, 1.5, 2])
    with cta_col:
        if st.button("Launch App", type="primary", use_container_width=True, key="launch_cta"):
            st.session_state["view_mode"] = "workspace"
            st.query_params["view"] = "workspace"
            st.rerun()

    st.markdown("")

    # ── Features ──
    st.markdown("""
    <div class="qm-section-heading" id="features">
        <h2>Engineered for precision</h2>
        <p>Every layer designed to make data querying safe, fast, and intelligent</p>
    </div>

    <div class="qm-features">
        <div class="qm-feature-card">
            <div class="icon">&#9881;</div>
            <h3>3-Stage Pipeline</h3>
            <p>Generate, validate, and execute SQL through a rigorous multi-step process with automatic self-correction on failures.</p>
        </div>
        <div class="qm-feature-card">
            <div class="icon">&#128274;</div>
            <h3>AST Safety Gate</h3>
            <p>Every query is parsed into an abstract syntax tree via sqlglot. Only SELECT statements pass. DDL, DML, and injections are structurally blocked.</p>
        </div>
        <div class="qm-feature-card">
            <div class="icon">&#9889;</div>
            <h3>Cost Gating</h3>
            <p>PostgreSQL EXPLAIN analysis blocks expensive queries before execution. Statement timeouts provide a hard backstop.</p>
        </div>
        <div class="qm-feature-card">
            <div class="icon">&#128200;</div>
            <h3>Result Validation</h3>
            <p>Great Expectations validates every result set against data quality rules before returning to the user.</p>
        </div>
        <div class="qm-feature-card">
            <div class="icon">&#128161;</div>
            <h3>Adaptive Learning</h3>
            <p>User corrections become few-shot examples automatically. The system learns from its mistakes and improves over time.</p>
        </div>
        <div class="qm-feature-card">
            <div class="icon">&#128203;</div>
            <h3>Full Audit Trail</h3>
            <p>Every query attempt is logged — NL input, generated SQL, EXPLAIN cost, execution time, and validation results.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Tech Stack ──
    st.markdown("""
    <div class="qm-section-heading" id="tech-stack">
        <h2>Built with modern tools</h2>
        <p>A carefully chosen stack for reliability and performance</p>
    </div>

    <div class="qm-tech-grid">
        <span class="qm-tech-pill">Python 3.11+</span>
        <span class="qm-tech-pill">FastAPI</span>
        <span class="qm-tech-pill">PostgreSQL 16</span>
        <span class="qm-tech-pill">SQLAlchemy 2.0</span>
        <span class="qm-tech-pill">Alembic</span>
        <span class="qm-tech-pill">LangChain</span>
        <span class="qm-tech-pill">OpenAI GPT-4o</span>
        <span class="qm-tech-pill">sqlglot</span>
        <span class="qm-tech-pill">Great Expectations</span>
        <span class="qm-tech-pill">Streamlit</span>
        <span class="qm-tech-pill">Docker</span>
        <span class="qm-tech-pill">Railway</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Security ──
    st.markdown("""
    <div class="qm-section-heading" id="security">
        <h2>Defense in depth</h2>
        <p>Multiple independent security layers — no single point of failure</p>
    </div>

    <div class="qm-security-grid">
        <div class="qm-security-item">
            <div class="dot"></div>
            <div class="text">
                <h4>SELECT-Only Enforcement</h4>
                <p>sqlglot AST parsing rejects all DDL/DML at the structural level</p>
            </div>
        </div>
        <div class="qm-security-item">
            <div class="dot"></div>
            <div class="text">
                <h4>Read-Only Database Role</h4>
                <p>Dedicated PostgreSQL role with no write permissions</p>
            </div>
        </div>
        <div class="qm-security-item">
            <div class="dot"></div>
            <div class="text">
                <h4>Single Statement Guard</h4>
                <p>Multi-statement batches are rejected before execution</p>
            </div>
        </div>
        <div class="qm-security-item">
            <div class="dot"></div>
            <div class="text">
                <h4>EXPLAIN Cost Gate</h4>
                <p>Expensive queries blocked via cost and row-estimate thresholds</p>
            </div>
        </div>
        <div class="qm-security-item">
            <div class="dot"></div>
            <div class="text">
                <h4>Statement Timeout</h4>
                <p>Hard time limit prevents runaway queries from consuming resources</p>
            </div>
        </div>
        <div class="qm-security-item">
            <div class="dot"></div>
            <div class="text">
                <h4>Row Limit Enforcement</h4>
                <p>Service-enforced LIMIT cap prevents unbounded result sets</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Footer ──
    st.markdown("""
    <div class="qm-footer">
        <p>QueryMind &mdash; Designed for precision.
        <a href="https://github.com/syedshabeebnibras/QueryMind" target="_blank">GitHub</a></p>
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# VIEW: WORKSPACE
# ══════════════════════════════════════════════════════════════
def _render_workspace():
    """Render the functional query workspace."""

    # ── Workspace header ──
    hdr_left, hdr_right = st.columns([3, 1])
    with hdr_left:
        st.markdown("""
        <div class="qm-ws-header">
            <div class="brand">
                <div class="brand-icon">Q</div>
                <span class="brand-text">QueryMind</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with hdr_right:
        if st.button("Home", key="back_home", use_container_width=True):
            st.session_state["view_mode"] = "landing"
            st.query_params["view"] = "landing"
            st.rerun()

    # ── Sidebar ──
    with st.sidebar:
        # Status
        try:
            health = asyncio.run(health_check())
            if health["status"] == "ok":
                st.markdown(
                    '<div class="qm-status-pill online">Connected</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="qm-status-pill offline">DB: {health["database"]}</div>',
                    unsafe_allow_html=True,
                )
        except Exception:
            st.markdown(
                '<div class="qm-status-pill offline">Offline</div>',
                unsafe_allow_html=True,
            )

        # User identity
        st.markdown('<div class="qm-section-label">Identity</div>', unsafe_allow_html=True)
        current_user = _user_param or ""
        new_user = st.text_input(
            "Username",
            value=current_user,
            key="username_input",
            placeholder="Enter your name",
            label_visibility="collapsed",
        )
        if new_user and new_user != current_user:
            st.query_params["user"] = new_user
            st.rerun()
        if current_user:
            st.markdown(
                f'<div class="qm-user-badge">{current_user}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Connection
        st.markdown('<div class="qm-section-label">Connection</div>', unsafe_allow_html=True)
        try:
            connections = asyncio.run(get_connections())
        except Exception:
            connections = []

        if connections:
            conn_names = [c["name"] for c in connections]
            selected_idx = st.selectbox(
                "Database",
                range(len(conn_names)),
                format_func=lambda i: conn_names[i],
                key="conn_select",
                label_visibility="collapsed",
            )
            selected_connection = connections[selected_idx]
        else:
            selected_connection = None
            st.caption("No connections yet")

        with st.expander("Manage", expanded=False):
            new_name = st.text_input("Name", key="new_conn_name", placeholder="production_db")
            new_url = st.text_input("URL", key="new_conn_url", type="password", placeholder="postgresql://...")
            if st.button("Add", key="add_conn_btn", use_container_width=True):
                if new_name and new_url:
                    try:
                        asyncio.run(create_connection(new_name, new_url))
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
                else:
                    st.warning("Both fields required.")

            if connections and len(connections) > 1:
                st.markdown("---")
                rm_names = [c["name"] for c in connections]
                rm_idx = st.selectbox(
                    "Remove",
                    range(len(rm_names)),
                    format_func=lambda i: rm_names[i],
                    key="rm_conn",
                )
                if st.button("Remove", key="rm_conn_btn", use_container_width=True):
                    try:
                        asyncio.run(delete_connection(connections[rm_idx]["id"]))
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

        st.markdown("---")

        # Tables
        conn_id = selected_connection["id"] if selected_connection else None
        try:
            existing_tables = asyncio.run(get_tables(connection_id=conn_id))
        except Exception:
            existing_tables = []

        if existing_tables:
            st.markdown(
                f'<div class="qm-section-label">Tables ({len(existing_tables)})</div>',
                unsafe_allow_html=True,
            )
            for t in existing_tables:
                st.markdown(
                    f'<div class="qm-table-item"><code>{t["table_name"]}</code>'
                    f'<span class="cols">{t["column_count"]} cols</span></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        # History
        st.markdown('<div class="qm-section-label">History</div>', unsafe_allow_html=True)
        status_filter = st.selectbox(
            "Filter",
            [None, "success", "error", "blocked"],
            format_func=lambda x: "All" if x is None else x.title(),
            label_visibility="collapsed",
        )
        if st.button("Load", key="load_hist", use_container_width=True):
            try:
                history = asyncio.run(
                    get_history(status=status_filter, user_id=st.session_state["user_id"])
                )
                for item in history["items"]:
                    label = item["nl_query"][:50]
                    status = item["status"]
                    with st.expander(f"{label}... ({status})"):
                        if item["final_sql"]:
                            st.code(item["final_sql"], language="sql")
                        st.caption(
                            f"{item['row_count']} rows"
                            + (f" | {item['runtime_ms']:.0f}ms" if item["runtime_ms"] else "")
                        )
            except Exception as e:
                st.error(str(e))

    # ── Query input ──
    nl_query = st.text_area(
        "What would you like to know?",
        placeholder="e.g., Show the top 10 customers by total spend last quarter",
        height=120,
        label_visibility="collapsed",
    )

    # ── Data import ──
    with st.expander("Import data", expanded=False):
        data_input = st.text_area(
            "Paste table data (CSV, TSV, markdown) or SQL (CREATE TABLE, INSERT):",
            height=180,
            key="data_input",
            placeholder="""Paste CSV / markdown table:
Date,Widget_Type,Daily_Production
2019-12-01,A,30
2019-12-02,A,30

Or SQL:
CREATE TABLE widgets (date DATE, type VARCHAR(10), count INTEGER);
INSERT INTO widgets VALUES ('2019-12-01', 'A', 30);""",
        )

        is_sql_input = False
        if data_input and data_input.strip():
            first_word = data_input.strip().split()[0].upper() if data_input.strip() else ""
            is_sql_input = first_word in ("CREATE", "INSERT", "ALTER", "DROP", "BEGIN", "WITH")

        if not is_sql_input:
            table_name = st.text_input(
                "Table name",
                value="user_table",
                key="table_name_input",
                placeholder="my_table",
            )

        col_import, _ = st.columns([1, 3])
        with col_import:
            if st.button("Import", key="import_btn", use_container_width=True):
                if data_input and data_input.strip():
                    conn_id = selected_connection["id"] if selected_connection else None
                    with st.spinner("Importing..."):
                        try:
                            if is_sql_input:
                                result = asyncio.run(
                                    setup_schema(data_input.strip(), connection_id=conn_id)
                                )
                                if result["status"] == "success":
                                    st.success(
                                        f"{result['statements_executed']} statement(s) executed."
                                    )
                                else:
                                    st.error(result.get("error", "Import failed."))
                            else:
                                result = asyncio.run(
                                    import_table(
                                        data_input.strip(),
                                        table_name.strip(),
                                        connection_id=conn_id,
                                    )
                                )
                                if result["status"] == "success":
                                    st.success(
                                        f"**{result['table_name']}** created — "
                                        f"{len(result['columns'])} cols, ~{result['row_count']} rows"
                                    )
                                else:
                                    st.error(result.get("error", "Import failed."))
                        except Exception as e:
                            st.error(str(e))
                else:
                    st.warning("Paste some data or SQL first.")

        st.markdown("")
        uploaded_files = st.file_uploader(
            "Or upload files",
            type=["sql", "txt", "csv", "tsv"],
            key="file_upload",
            accept_multiple_files=True,
            label_visibility="visible",
        )
        if uploaded_files:
            cached_files = []
            for uf in uploaded_files:
                cache_key = f"file_cache_{uf.name}_{uf.size}"
                if cache_key not in st.session_state:
                    st.session_state[cache_key] = uf.read().decode("utf-8")
                cached_files.append((uf.name, st.session_state[cache_key]))

            for fname, content in cached_files:
                lines = content.strip().split("\n")
                st.caption(f"{fname} — {len(lines)} lines")

            if st.button("Import files", key="upload_import_btn", use_container_width=True):
                conn_id = selected_connection["id"] if selected_connection else None
                progress = st.progress(0, text="Importing...")
                total = len(cached_files)
                for idx, (fname, content) in enumerate(cached_files):
                    is_sql = fname.endswith(".sql")
                    tname = fname.rsplit(".", 1)[0].replace(" ", "_").replace("-", "_").lower()
                    progress.progress(idx / total, text=f"{fname}...")
                    try:
                        if is_sql:
                            result = asyncio.run(setup_schema(content, connection_id=conn_id))
                            if result["status"] == "success":
                                st.success(f"{fname}: {result['statements_executed']} statements")
                            else:
                                st.error(f"{fname}: {result.get('error')}")
                        else:
                            result = asyncio.run(
                                import_table(content, tname, connection_id=conn_id)
                            )
                            if result["status"] == "success":
                                st.success(
                                    f"{fname} -> **{result['table_name']}** "
                                    f"({len(result['columns'])} cols, ~{result['row_count']} rows)"
                                )
                            else:
                                st.error(f"{fname}: {result.get('error')}")
                    except Exception as e:
                        st.error(f"{fname}: {e}")
                progress.progress(1.0, text="Done!")
                st.rerun()

    # ── Run button ──
    if st.button("Run Query", type="primary", use_container_width=True):
        if nl_query and nl_query.strip():
            conn_id = selected_connection["id"] if selected_connection else None
            with st.spinner("Thinking..."):
                try:
                    result = asyncio.run(
                        run_query(
                            nl_query.strip(),
                            user_id=st.session_state["user_id"],
                            connection_id=conn_id,
                        )
                    )
                    st.session_state["last_result"] = result
                    st.session_state.pop("show_correction", None)
                except Exception as e:
                    st.session_state["last_result"] = None
                    st.error(str(e) or repr(e))
                    import traceback
                    with st.expander("Details"):
                        st.code(traceback.format_exc())
        else:
            st.warning("Enter a question first.")

    # ── Results ──
    result = st.session_state.get("last_result")
    if result and result["status"] == "success":
        st.markdown("---")

        st.markdown('<div class="qm-label">Generated SQL</div>', unsafe_allow_html=True)
        st.code(result["final_sql"], language="sql")

        # Metrics
        m_parts = []
        m_parts.append(f'<span class="val">{result["runtime_ms"]:.0f}ms</span> runtime')
        m_parts.append(f'<span class="val">{result["row_count"]}</span> rows')
        if result.get("explain_summary"):
            m_parts.append(f'cost <span class="val">{result["explain_summary"]["total_cost"]:.0f}</span>')
            m_parts.append(f'est. <span class="val">{result["explain_summary"]["estimated_rows"]:,}</span> rows')
        st.markdown(
            '<div class="qm-metrics-strip">' + " &middot; ".join(m_parts) + "</div>",
            unsafe_allow_html=True,
        )

        if result["rows"]:
            df = pd.DataFrame(result["rows"], columns=result["columns"])
            st.dataframe(df, use_container_width=True, hide_index=True)

            numeric_cols = df.select_dtypes(include="number").columns.tolist()
            if numeric_cols and len(df) > 1:
                non_numeric = [c for c in df.columns if c not in numeric_cols]
                if non_numeric:
                    chart_df = df.set_index(non_numeric[0])[numeric_cols]
                    st.bar_chart(chart_df)
                else:
                    st.bar_chart(df[numeric_cols])

        if result.get("validation_summary"):
            vs = result["validation_summary"]
            if vs["success"]:
                st.success(
                    f"Validation: {vs['expectations_passed']}/{vs['expectations_evaluated']} passed"
                )
            else:
                st.warning(
                    f"Validation: {vs['expectations_passed']}/{vs['expectations_evaluated']} passed"
                )
                for detail in vs.get("details", []):
                    if not detail["success"]:
                        st.caption(f"Failed: {detail['expectation']}")

        if len(result.get("attempted_sqls", [])) > 1:
            with st.expander("Self-correction attempts"):
                for i, sql in enumerate(result["attempted_sqls"]):
                    st.caption(f"Attempt {i + 1}")
                    st.code(sql, language="sql")

        # Feedback
        st.markdown("")
        fc1, fc2, fc3 = st.columns([1, 1, 4])
        with fc1:
            if st.button("Good", key="good_feedback", use_container_width=True):
                asyncio.run(submit_feedback(result["query_id"], rating=5))
                st.toast("Thanks for the feedback!")
        with fc2:
            if st.button("Bad", key="bad_feedback", use_container_width=True):
                st.session_state["show_correction"] = True

        if st.session_state.get("show_correction"):
            corrected = st.text_area(
                "Correct SQL:",
                height=150,
                key="corrected_sql",
                placeholder="SELECT ...",
            )
            notes = st.text_input("What was wrong?", key="feedback_notes")
            if st.button("Submit correction", key="submit_correction"):
                asyncio.run(
                    submit_feedback(
                        result["query_id"],
                        rating=1,
                        corrected_sql=corrected or None,
                        notes=notes or None,
                    )
                )
                st.toast("Correction saved!")
                st.session_state["show_correction"] = False
                st.rerun()

    elif result and result["status"] != "success":
        st.markdown("---")
        st.error(f"Query failed: {result.get('error', 'Unknown error')}")
        if result.get("attempted_sqls"):
            with st.expander("Attempted SQL"):
                for i, sql in enumerate(result["attempted_sqls"]):
                    st.caption(f"Attempt {i + 1}")
                    st.code(sql, language="sql")


# ══════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════
if st.session_state["view_mode"] == "workspace":
    _render_workspace()
else:
    _render_landing()
