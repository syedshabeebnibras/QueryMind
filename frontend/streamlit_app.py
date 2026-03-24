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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        /* ── Typography ── */
        --font-weight-normal: 400;
        --font-weight-medium: 500;

        /* ── Syntactic Slate — Core palette ── */
        --background:       #0a0a0b;
        --foreground:        #e8e8ea;
        --card:              #16161a;
        --popover:           #1c1c21;
        --surface-elevated:  #1c1c21;
        --surface-base:      #16161a;
        --surface-sunken:    #0a0a0b;

        /* ── Accent & semantic ── */
        --primary:           #e8e8ea;
        --secondary:         #1f1f24;
        --muted:             #28282e;
        --accent:            #2c2c34;
        --destructive:       #ff3b30;

        /* ── Borders & inputs ── */
        --border:            rgba(255, 255, 255, 0.08);
        --input:             rgba(255, 255, 255, 0.05);
        --input-background:  #1c1c21;
        --switch-background: #3a3a40;
        --ring:              rgba(255, 255, 255, 0.15);

        /* ── Chart colors ── */
        --chart-1: #007aff;
        --chart-2: #5e5ce6;
        --chart-3: #30d158;
        --chart-4: #ff9f0a;
        --chart-5: #ff375f;

        /* ── Premium effects ── */
        --glow-primary:      rgba(0, 122, 255, 0.15);
        --glow-accent:       rgba(94, 92, 230, 0.12);

        /* ── Radius ── */
        --radius:            0.75rem;

        /* ── Mapped aliases (used by component CSS) ── */
        --qm-bg-deep:       var(--background);
        --qm-bg-base:       var(--surface-sunken);
        --qm-bg-raised:     var(--card);
        --qm-bg-surface:    var(--surface-elevated);
        --qm-bg-hover:      var(--muted);
        --qm-bg-elevated:   var(--accent);
        --qm-border:        var(--border);
        --qm-border-hover:  rgba(255, 255, 255, 0.12);
        --qm-border-focus:  var(--ring);
        --qm-text-primary:  var(--foreground);
        --qm-text-secondary: rgba(232, 232, 234, 0.55);
        --qm-text-tertiary: rgba(232, 232, 234, 0.3);
        --qm-text-ghost:    rgba(232, 232, 234, 0.15);
        --qm-accent:        #9da3ad;
        --qm-accent-bright: #b8bcc5;
        --qm-accent-glow:   rgba(157, 163, 173, 0.08);
        --qm-green:         var(--chart-3);
        --qm-green-bg:      rgba(48, 209, 88, 0.06);
        --qm-red:           var(--destructive);
        --qm-red-bg:        rgba(255, 59, 48, 0.06);
        --qm-radius-sm:     var(--radius);
        --qm-radius-md:     calc(var(--radius) + 2px);
        --qm-radius-lg:     calc(var(--radius) + 6px);
        --qm-radius-xl:     calc(var(--radius) + 12px);
        --qm-font:          'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
                             'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
                             'Helvetica Neue', sans-serif;
        --qm-spring:        cubic-bezier(0.175, 0.885, 0.32, 1.275);
        --qm-spring-soft:   cubic-bezier(0.16, 1, 0.3, 1);
        --qm-ease:          cubic-bezier(0.4, 0, 0.2, 1);
        --qm-ease-out:      cubic-bezier(0, 0, 0.2, 1);
        --qm-shadow-sm:     0 1px 2px rgba(0,0,0,0.3), 0 1px 3px rgba(0,0,0,0.15);
        --qm-shadow-md:     0 4px 16px rgba(0,0,0,0.25), 0 2px 4px rgba(0,0,0,0.15);
        --qm-shadow-lg:     0 12px 40px rgba(0,0,0,0.35), 0 4px 12px rgba(0,0,0,0.2);
        --qm-shadow-glow:   0 0 20px rgba(157, 163, 173, 0.04), 0 0 40px rgba(157, 163, 173, 0.02);
    }

    /* ── Utility classes ── */
    .glass-surface {
        background: rgba(22, 22, 26, 0.55) !important;
        backdrop-filter: blur(24px) saturate(1.4) !important;
        -webkit-backdrop-filter: blur(24px) saturate(1.4) !important;
        border: 0.5px solid var(--border) !important;
    }
    .premium-glow {
        box-shadow: 0 0 20px var(--glow-primary), 0 0 40px var(--glow-accent);
    }
    .subtle-glow {
        box-shadow: 0 0 15px var(--glow-primary);
    }
    .elevated-surface {
        background: var(--surface-elevated);
        border: 0.5px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--qm-shadow-md);
    }
    .premium-border {
        border: 0.5px solid var(--border);
        border-radius: var(--radius);
    }

    /* ── Reset ── */
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        font-family: var(--qm-font);
        font-weight: var(--font-weight-normal);
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }
    [data-testid="stAppViewContainer"],
    [data-testid="stApp"] {
        background: var(--background);
        background-image:
            radial-gradient(ellipse 80% 50% at 50% -20%, rgba(0,122,255,0.03) 0%, transparent 70%),
            radial-gradient(ellipse 60% 40% at 80% 60%, rgba(94,92,230,0.02) 0%, transparent 60%);
    }

    /* ── Keyframes ── */
    @keyframes fadeSlideUp {
        from { opacity: 0; transform: translateY(24px) scale(0.98); }
        to   { opacity: 1; transform: translateY(0) scale(1); }
    }
    @keyframes fadeSlideDown {
        from { opacity: 0; transform: translateY(-12px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
    }
    @keyframes scaleIn {
        from { opacity: 0; transform: scale(0.92); }
        to   { opacity: 1; transform: scale(1); }
    }
    @keyframes shimmer {
        0%   { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    @keyframes pulseGlow {
        0%, 100% { box-shadow: 0 0 15px var(--glow-primary); }
        50%      { box-shadow: 0 0 30px var(--glow-primary), 0 0 60px var(--glow-accent); }
    }
    @keyframes borderGlow {
        0%, 100% { border-color: var(--border); }
        50%      { border-color: rgba(0, 122, 255, 0.15); }
    }
    @keyframes float {
        0%, 100% { transform: translateY(0); }
        50%      { transform: translateY(-4px); }
    }
    @keyframes revealLine {
        from { width: 0; opacity: 0; }
        to   { width: 100%; opacity: 1; }
    }
    @keyframes dotPulse {
        0%, 100% { box-shadow: 0 0 4px var(--glow-primary); }
        50%      { box-shadow: 0 0 12px var(--glow-primary), 0 0 20px var(--glow-accent); }
    }

    /* ── Landing nav ── */
    .qm-landing-nav {
        display: flex; align-items: center; justify-content: space-between;
        padding: 1rem 3rem;
        position: sticky; top: 0; z-index: 100;
        background: rgba(8, 8, 10, 0.6);
        backdrop-filter: blur(24px) saturate(1.4);
        -webkit-backdrop-filter: blur(24px) saturate(1.4);
        border-bottom: 0.5px solid var(--qm-border);
        animation: fadeSlideDown 0.5s var(--qm-spring-soft) both;
    }
    .qm-landing-nav .brand {
        display: flex; align-items: center; gap: 10px;
        text-decoration: none;
        transition: opacity 0.2s ease;
    }
    .qm-landing-nav .brand:hover { opacity: 0.85; }
    .qm-landing-nav .brand-icon {
        width: 34px; height: 34px;
        border-radius: 9px;
        background: linear-gradient(145deg, var(--qm-bg-surface) 0%, var(--qm-bg-raised) 100%);
        border: 0.5px solid rgba(255,255,255,0.06);
        display: flex; align-items: center; justify-content: center;
        font-size: 0.9rem; font-weight: 700; color: var(--qm-accent-bright);
        box-shadow: var(--qm-shadow-sm), inset 0 1px 0 rgba(255,255,255,0.04);
        transition: all 0.3s var(--qm-spring);
    }
    .qm-landing-nav .brand:hover .brand-icon {
        box-shadow: var(--qm-shadow-md), inset 0 1px 0 rgba(255,255,255,0.06);
        transform: scale(1.05);
    }
    .qm-landing-nav .brand-text {
        font-size: 1.05rem; font-weight: 650;
        color: var(--qm-text-primary);
        letter-spacing: -0.4px;
    }
    .qm-landing-nav .nav-links {
        display: flex; gap: 2.25rem; align-items: center;
    }
    .qm-landing-nav .nav-links a {
        font-size: 0.8rem; font-weight: 450;
        color: var(--qm-text-tertiary);
        text-decoration: none; letter-spacing: 0.3px;
        padding: 4px 0;
        position: relative;
        transition: color 0.25s var(--qm-ease);
    }
    .qm-landing-nav .nav-links a::after {
        content: '';
        position: absolute; bottom: -2px; left: 0; right: 0;
        height: 1px;
        background: var(--chart-1);
        transform: scaleX(0);
        transition: transform 0.25s var(--qm-spring);
        transform-origin: center;
    }
    .qm-landing-nav .nav-links a:hover {
        color: var(--qm-text-primary);
    }
    .qm-landing-nav .nav-links a:hover::after {
        transform: scaleX(1);
    }

    /* ── Hero ── */
    .qm-landing-hero {
        text-align: center;
        padding: 7rem 2rem 4.5rem 2rem;
        max-width: 760px;
        margin: 0 auto;
        position: relative;
        animation: fadeSlideUp 0.7s 0.15s var(--qm-spring-soft) both;
    }
    .qm-landing-hero::before {
        content: '';
        position: absolute;
        top: -60px; left: 50%;
        transform: translateX(-50%);
        width: 500px; height: 400px;
        background: radial-gradient(ellipse, rgba(157,163,173,0.04) 0%, transparent 70%);
        pointer-events: none;
    }
    .qm-landing-hero .badge {
        display: inline-flex; align-items: center; gap: 6px;
        font-size: 0.68rem; font-weight: 550;
        letter-spacing: 1.2px; text-transform: uppercase;
        color: var(--chart-1);
        background: linear-gradient(135deg, rgba(0,122,255,0.1) 0%, rgba(94,92,230,0.06) 100%);
        border: 0.5px solid rgba(0, 122, 255, 0.15);
        padding: 6px 16px;
        border-radius: 24px;
        margin-bottom: 2rem;
        animation: pulseGlow 4s ease infinite;
        backdrop-filter: blur(8px);
    }
    .qm-landing-hero .badge::before {
        content: '';
        width: 5px; height: 5px;
        border-radius: 50%;
        background: var(--chart-1);
        animation: dotPulse 2s ease infinite;
    }
    .qm-landing-hero h1 {
        font-size: 3.5rem; font-weight: 800;
        letter-spacing: -2px; line-height: 1.06;
        color: var(--qm-text-primary);
        margin: 0 0 1.5rem 0;
    }
    .qm-landing-hero h1 .gradient-text {
        background: linear-gradient(
            135deg,
            #e8e8ea 0%,
            #007aff 25%,
            #5e5ce6 50%,
            #007aff 75%,
            #e8e8ea 100%
        );
        background-size: 300% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: shimmer 8s ease infinite;
    }
    .qm-landing-hero p {
        font-size: 1.1rem; font-weight: 400;
        color: var(--qm-text-secondary);
        line-height: 1.7;
        margin: 0 auto 3rem auto;
        max-width: 540px;
    }

    /* ── CTA ── */
    .qm-cta-wrap {
        display: flex; justify-content: center; gap: 0.75rem;
        animation: fadeSlideUp 0.6s 0.35s var(--qm-spring-soft) both;
    }

    /* ── Feature cards ── */
    .qm-features {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
        max-width: 940px;
        margin: 0 auto;
        padding: 0 2rem 5rem 2rem;
    }
    .qm-feature-card {
        background: linear-gradient(180deg, rgba(22,22,25,0.8) 0%, rgba(22,22,25,0.4) 100%);
        border: 0.5px solid var(--qm-border);
        border-radius: var(--qm-radius-lg);
        padding: 2rem 1.5rem;
        position: relative;
        overflow: hidden;
        transition: all 0.4s var(--qm-spring-soft);
        animation: fadeSlideUp 0.55s var(--qm-spring-soft) both;
        backdrop-filter: blur(8px);
    }
    .qm-feature-card::before {
        content: '';
        position: absolute; top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0,122,255,0.15), transparent);
        opacity: 0;
        transition: opacity 0.4s ease;
    }
    .qm-feature-card::after {
        content: '';
        position: absolute; inset: 0;
        border-radius: var(--qm-radius-lg);
        background: radial-gradient(ellipse at 50% 0%, rgba(0,122,255,0.04) 0%, transparent 60%);
        opacity: 0;
        transition: opacity 0.4s ease;
        pointer-events: none;
    }
    .qm-feature-card:nth-child(1) { animation-delay: 0.1s; }
    .qm-feature-card:nth-child(2) { animation-delay: 0.18s; }
    .qm-feature-card:nth-child(3) { animation-delay: 0.26s; }
    .qm-feature-card:nth-child(4) { animation-delay: 0.34s; }
    .qm-feature-card:nth-child(5) { animation-delay: 0.42s; }
    .qm-feature-card:nth-child(6) { animation-delay: 0.5s; }
    .qm-feature-card:hover {
        border-color: rgba(0,122,255,0.15);
        transform: translateY(-4px) scale(1.02);
        box-shadow: var(--qm-shadow-lg), 0 0 20px var(--glow-primary);
    }
    .qm-feature-card:hover::before,
    .qm-feature-card:hover::after { opacity: 1; }
    .qm-feature-card .icon {
        width: 40px; height: 40px;
        border-radius: 11px;
        background: linear-gradient(145deg, var(--qm-bg-surface), var(--qm-bg-elevated));
        border: 0.5px solid rgba(255,255,255,0.05);
        display: flex; align-items: center; justify-content: center;
        font-size: 1.05rem;
        margin-bottom: 1.25rem;
        box-shadow: var(--qm-shadow-sm);
        transition: all 0.35s var(--qm-spring);
    }
    .qm-feature-card:hover .icon {
        transform: scale(1.08) translateY(-2px);
        box-shadow: var(--qm-shadow-md);
    }
    .qm-feature-card h3 {
        font-size: 0.9rem; font-weight: 620;
        color: var(--qm-text-primary);
        margin: 0 0 0.5rem 0;
        letter-spacing: -0.2px;
        transition: color 0.2s ease;
    }
    .qm-feature-card:hover h3 { color: #fff; }
    .qm-feature-card p {
        font-size: 0.8rem; font-weight: 400;
        color: var(--qm-text-secondary);
        line-height: 1.6; margin: 0;
    }

    /* ── Section headings ── */
    .qm-section-heading {
        text-align: center;
        padding: 4rem 2rem 2.5rem 2rem;
        animation: fadeSlideUp 0.55s var(--qm-spring-soft) both;
    }
    .qm-section-heading h2 {
        font-size: 1.75rem; font-weight: 750;
        letter-spacing: -1px;
        color: var(--qm-text-primary);
        margin: 0 0 0.6rem 0;
    }
    .qm-section-heading p {
        font-size: 0.9rem;
        color: var(--qm-text-tertiary);
        margin: 0;
    }

    /* ── Tech pills ── */
    .qm-tech-grid {
        display: flex; flex-wrap: wrap; gap: 0.6rem;
        justify-content: center;
        max-width: 720px;
        margin: 0 auto;
        padding: 0 2rem 5rem 2rem;
        animation: fadeSlideUp 0.5s 0.2s var(--qm-spring-soft) both;
    }
    .qm-tech-pill {
        font-size: 0.76rem; font-weight: 500;
        color: var(--qm-text-secondary);
        background: var(--qm-bg-raised);
        border: 0.5px solid var(--qm-border);
        padding: 7px 16px;
        border-radius: 22px;
        letter-spacing: 0.2px;
        transition: all 0.3s var(--qm-spring-soft);
        cursor: default;
    }
    .qm-tech-pill:hover {
        border-color: rgba(157,163,173,0.15);
        color: var(--qm-text-primary);
        background: var(--qm-bg-hover);
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }

    /* ── Security grid ── */
    .qm-security-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.75rem;
        max-width: 720px;
        margin: 0 auto;
        padding: 0 2rem 5rem 2rem;
        animation: fadeSlideUp 0.5s 0.2s var(--qm-spring-soft) both;
    }
    .qm-security-item {
        display: flex; gap: 0.75rem; align-items: flex-start;
        padding: 1.15rem 1.25rem;
        background: linear-gradient(180deg, var(--qm-bg-raised) 0%, rgba(22,22,25,0.6) 100%);
        border: 0.5px solid var(--qm-border);
        border-radius: var(--qm-radius-md);
        transition: all 0.35s var(--qm-spring-soft);
        backdrop-filter: blur(4px);
    }
    .qm-security-item:hover {
        border-color: rgba(157,163,173,0.1);
        transform: translateY(-2px) scale(1.01);
        box-shadow: var(--qm-shadow-md);
    }
    .qm-security-item .dot {
        width: 6px; height: 6px;
        border-radius: 50%;
        background: var(--chart-1);
        margin-top: 7px;
        flex-shrink: 0;
        box-shadow: 0 0 8px var(--glow-primary);
        animation: dotPulse 3s ease infinite;
    }
    .qm-security-item:nth-child(2) .dot { animation-delay: 0.5s; }
    .qm-security-item:nth-child(3) .dot { animation-delay: 1s; }
    .qm-security-item:nth-child(4) .dot { animation-delay: 1.5s; }
    .qm-security-item:nth-child(5) .dot { animation-delay: 2s; }
    .qm-security-item:nth-child(6) .dot { animation-delay: 2.5s; }
    .qm-security-item .text h4 {
        font-size: 0.84rem; font-weight: 600;
        color: var(--qm-text-primary);
        margin: 0 0 0.3rem 0;
    }
    .qm-security-item .text p {
        font-size: 0.76rem;
        color: var(--qm-text-tertiary);
        margin: 0; line-height: 1.55;
    }

    /* ── Footer ── */
    .qm-footer {
        text-align: center;
        padding: 3.5rem 2rem;
        border-top: 0.5px solid var(--qm-border);
        animation: fadeIn 0.5s 0.4s var(--qm-spring-soft) both;
        position: relative;
    }
    .qm-footer::before {
        content: '';
        position: absolute; top: 0; left: 50%;
        transform: translateX(-50%);
        width: 200px; height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0,122,255,0.2), transparent);
    }
    .qm-footer p {
        font-size: 0.76rem;
        color: var(--qm-text-ghost);
        margin: 0; letter-spacing: 0.3px;
    }
    .qm-footer a {
        color: var(--qm-text-tertiary);
        text-decoration: none;
        transition: color 0.2s ease;
        position: relative;
    }
    .qm-footer a::after {
        content: '';
        position: absolute; bottom: -1px; left: 0; right: 0;
        height: 0.5px; background: var(--chart-1);
        transform: scaleX(0);
        transition: transform 0.25s var(--qm-spring);
    }
    .qm-footer a:hover { color: var(--qm-text-secondary); }
    .qm-footer a:hover::after { transform: scaleX(1); }

    /* ── Workspace header ── */
    .qm-ws-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 0 0 1.5rem 0;
        animation: fadeSlideDown 0.45s var(--qm-spring-soft) both;
    }
    .qm-ws-header .brand {
        display: flex; align-items: center; gap: 10px;
    }
    .qm-ws-header .brand-icon {
        width: 30px; height: 30px;
        border-radius: 8px;
        background: linear-gradient(145deg, var(--qm-bg-surface), var(--qm-bg-raised));
        border: 0.5px solid var(--qm-border);
        display: flex; align-items: center; justify-content: center;
        font-size: 0.78rem; font-weight: 700; color: var(--qm-accent-bright);
        box-shadow: var(--qm-shadow-sm);
        transition: all 0.3s var(--qm-spring);
    }
    .qm-ws-header .brand-icon:hover {
        transform: scale(1.08);
    }
    .qm-ws-header .brand-text {
        font-size: 0.92rem; font-weight: 620;
        color: var(--qm-text-primary);
        letter-spacing: -0.3px;
    }

    /* ── Inputs ── */
    .stTextArea textarea,
    .stTextInput input {
        background: var(--qm-bg-raised) !important;
        border: 0.5px solid var(--qm-border) !important;
        border-radius: var(--qm-radius-sm) !important;
        color: var(--qm-text-primary) !important;
        font-family: var(--qm-font) !important;
        font-size: 0.88rem !important;
        padding: 0.9rem 1.1rem !important;
        transition: border-color 0.3s var(--qm-spring-soft),
                    box-shadow 0.3s var(--qm-spring-soft),
                    background 0.3s ease !important;
        caret-color: var(--qm-accent-bright) !important;
    }
    .stTextArea textarea:focus,
    .stTextInput input:focus {
        border-color: var(--qm-border-focus) !important;
        background: var(--qm-bg-surface) !important;
        box-shadow: 0 0 0 3px rgba(157, 163, 173, 0.06),
                    0 2px 8px rgba(0,0,0,0.2),
                    inset 0 0 0 0.5px rgba(157, 163, 173, 0.1) !important;
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
        background: linear-gradient(180deg, #2c2c32 0%, #222226 100%) !important;
        border: 0.5px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: var(--qm-radius-sm) !important;
        color: var(--qm-text-primary) !important;
        font-family: var(--qm-font) !important;
        font-weight: 550 !important;
        font-size: 0.86rem !important;
        letter-spacing: 0.1px !important;
        padding: 0.7rem 1.5rem !important;
        position: relative !important;
        overflow: hidden !important;
        transition: all 0.25s var(--qm-spring-soft) !important;
        box-shadow: var(--qm-shadow-sm),
                    inset 0 1px 0 rgba(255,255,255,0.05) !important;
    }
    .stButton > button[kind="primary"]::before,
    .stButton > button[data-testid="stBaseButton-primary"]::before {
        content: '';
        position: absolute; inset: 0;
        background: linear-gradient(180deg, rgba(255,255,255,0.03) 0%, transparent 50%);
        pointer-events: none;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(180deg, #333338 0%, #2a2a2f 100%) !important;
        border-color: rgba(255, 255, 255, 0.12) !important;
        box-shadow: var(--qm-shadow-md),
                    inset 0 1px 0 rgba(255,255,255,0.07),
                    0 0 20px var(--glow-primary) !important;
        transform: translateY(-1px) !important;
    }
    .stButton > button[kind="primary"]:active,
    .stButton > button[data-testid="stBaseButton-primary"]:active {
        transform: scale(0.95) translateY(0) !important;
        box-shadow: 0 0 0 rgba(0,0,0,0.1),
                    inset 0 2px 4px rgba(0,0,0,0.2) !important;
        transition-duration: 0.1s !important;
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
        padding: 0.55rem 1.25rem !important;
        transition: all 0.25s var(--qm-spring-soft) !important;
        position: relative !important;
        overflow: hidden !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="stBaseButton-secondary"]:hover,
    .stButton > button:not([kind]):hover {
        background: rgba(255, 255, 255, 0.03) !important;
        border-color: var(--qm-border-hover) !important;
        color: var(--qm-text-primary) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1) !important;
        transform: translateY(-0.5px) !important;
    }
    .stButton > button[kind="secondary"]:active,
    .stButton > button[data-testid="stBaseButton-secondary"]:active,
    .stButton > button:not([kind]):active {
        transform: scale(0.95) !important;
        transition-duration: 0.1s !important;
    }

    /* ── Expander — glass panel ── */
    .streamlit-expanderHeader {
        background: rgba(22, 22, 25, 0.5) !important;
        backdrop-filter: blur(16px) saturate(1.2) !important;
        -webkit-backdrop-filter: blur(16px) saturate(1.2) !important;
        border: 0.5px solid var(--qm-border) !important;
        border-radius: var(--qm-radius-sm) !important;
        font-family: var(--qm-font) !important;
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        color: var(--qm-text-secondary) !important;
        letter-spacing: 0.2px !important;
        padding: 0.75rem 1.1rem !important;
        transition: all 0.3s var(--qm-spring-soft) !important;
    }
    .streamlit-expanderHeader:hover {
        border-color: var(--qm-border-hover) !important;
        color: var(--qm-text-primary) !important;
        background: rgba(28, 28, 32, 0.7) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.12) !important;
    }
    [data-testid="stExpander"] {
        border: 0.5px solid rgba(255, 255, 255, 0.03) !important;
        border-radius: var(--qm-radius-sm) !important;
        overflow: hidden;
        transition: all 0.3s var(--qm-spring-soft);
    }
    [data-testid="stExpander"]:hover {
        border-color: rgba(255, 255, 255, 0.05) !important;
    }
    [data-testid="stExpander"] details {
        border: none !important;
    }

    /* ── Code blocks ── */
    .stCodeBlock, pre, code { border-radius: var(--qm-radius-sm) !important; }
    [data-testid="stCodeBlock"] {
        border: 0.5px solid rgba(255, 255, 255, 0.04) !important;
        border-radius: var(--qm-radius-sm) !important;
        overflow: hidden;
        box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
    }

    /* ── Dataframe ── */
    [data-testid="stDataFrame"] {
        border: 0.5px solid var(--qm-border) !important;
        border-radius: var(--qm-radius-md) !important;
        overflow: hidden;
        animation: scaleIn 0.45s var(--qm-spring-soft) both;
        box-shadow: var(--qm-shadow-sm);
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: rgba(10, 10, 12, 0.8) !important;
        backdrop-filter: blur(28px) saturate(1.3) !important;
        -webkit-backdrop-filter: blur(28px) saturate(1.3) !important;
        border-right: 0.5px solid var(--qm-border) !important;
    }

    /* ── Status pill ── */
    .qm-status-pill {
        display: inline-flex; align-items: center; gap: 6px;
        font-family: var(--qm-font);
        font-size: 0.68rem; font-weight: 550;
        letter-spacing: 0.6px; text-transform: uppercase;
        padding: 5px 14px; border-radius: 22px;
        transition: all 0.3s var(--qm-spring-soft);
    }
    .qm-status-pill.online {
        background: var(--qm-green-bg);
        color: var(--qm-green);
        border: 0.5px solid rgba(74, 222, 128, 0.1);
        box-shadow: 0 0 12px rgba(74, 222, 128, 0.06);
    }
    .qm-status-pill.online::before {
        content: '';
        width: 5px; height: 5px;
        border-radius: 50%;
        background: var(--qm-green);
        animation: dotPulse 2.5s ease infinite;
    }
    .qm-status-pill.offline {
        background: var(--qm-red-bg);
        color: var(--qm-red);
        border: 0.5px solid rgba(248, 113, 113, 0.1);
    }

    /* ── Sidebar labels ── */
    .qm-section-label {
        font-family: var(--qm-font);
        font-size: 0.6rem; font-weight: 650;
        letter-spacing: 1.8px; text-transform: uppercase;
        color: var(--qm-text-tertiary);
        margin: 1.25rem 0 0.5rem 0;
    }
    .qm-table-item {
        font-family: var(--qm-font); font-size: 0.8rem;
        color: var(--qm-text-secondary);
        padding: 4px 0;
        transition: color 0.2s ease;
    }
    .qm-table-item:hover { color: var(--qm-text-primary); }
    .qm-table-item code {
        font-size: 0.76rem;
        color: rgba(240, 240, 243, 0.65);
        background: rgba(255, 255, 255, 0.04);
        padding: 2px 7px; border-radius: 5px;
        border: 0.5px solid var(--qm-border);
        transition: all 0.2s ease;
    }
    .qm-table-item:hover code {
        background: rgba(255, 255, 255, 0.06);
        border-color: var(--qm-border-hover);
    }
    .qm-table-item .cols {
        color: var(--qm-text-tertiary);
        font-size: 0.7rem; margin-left: 4px;
    }

    /* ── Result labels ── */
    .qm-label {
        font-family: var(--qm-font);
        font-size: 0.6rem; font-weight: 650;
        letter-spacing: 1.8px; text-transform: uppercase;
        color: var(--qm-text-tertiary);
        margin-bottom: 0.5rem;
    }

    /* ── Metrics strip ── */
    .qm-metrics-strip {
        display: flex; gap: 1.25rem; padding: 0.6rem 0;
        font-family: var(--qm-font);
        font-size: 0.76rem;
        color: var(--qm-text-tertiary);
        animation: fadeIn 0.5s 0.2s both;
    }
    .qm-metrics-strip .val {
        color: var(--qm-text-secondary);
        font-weight: 550;
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
        transition: all 0.25s ease !important;
    }
    [data-testid="stSelectbox"] > div > div:hover {
        border-color: var(--qm-border-hover) !important;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        border: 0.5px dashed rgba(255, 255, 255, 0.06) !important;
        border-radius: var(--qm-radius-sm) !important;
        transition: all 0.3s var(--qm-spring-soft) !important;
        padding: 1rem !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: rgba(157, 163, 173, 0.15) !important;
        background: rgba(255, 255, 255, 0.01) !important;
    }

    /* ── Alerts ── */
    [data-testid="stAlert"] {
        border-radius: var(--qm-radius-sm) !important;
        border-width: 0.5px !important;
        font-size: 0.84rem !important;
        backdrop-filter: blur(8px) !important;
    }

    /* ── Progress bar ── */
    .stProgress > div > div {
        background: rgba(157, 163, 173, 0.08) !important;
        border-radius: 6px !important;
        overflow: hidden;
    }
    .stProgress > div > div > div {
        background: linear-gradient(90deg, var(--chart-1), var(--chart-2), var(--chart-1)) !important;
        background-size: 200% auto !important;
        animation: shimmer 2s linear infinite !important;
        border-radius: 6px !important;
    }

    /* ── Toast ── */
    [data-testid="stToast"] {
        background: rgba(22, 22, 25, 0.85) !important;
        backdrop-filter: blur(16px) saturate(1.3) !important;
        border: 0.5px solid var(--qm-border) !important;
        border-radius: var(--qm-radius-md) !important;
        box-shadow: var(--qm-shadow-lg) !important;
        animation: scaleIn 0.35s var(--qm-spring) both !important;
    }

    /* ── Charts ── */
    [data-testid="stVegaLiteChart"] {
        border: 0.5px solid rgba(255, 255, 255, 0.03) !important;
        border-radius: var(--qm-radius-md) !important;
        overflow: hidden; padding: 0.75rem;
        background: rgba(22, 22, 25, 0.3) !important;
        animation: fadeSlideUp 0.4s 0.1s var(--qm-spring-soft) both;
    }

    .stCaption, [data-testid="stCaption"] {
        font-family: var(--qm-font) !important;
    }

    /* ── Workspace-specific panels ── */
    .qm-ws-topbar {
        display: flex; align-items: center; justify-content: space-between;
        padding: 0.75rem 0 1.5rem 0;
        animation: fadeSlideDown 0.45s var(--qm-spring-soft) both;
        border-bottom: 0.5px solid var(--border);
        margin-bottom: 1.5rem;
    }
    .qm-ws-topbar .brand {
        display: flex; align-items: center; gap: 12px;
        text-decoration: none;
    }
    .qm-ws-topbar .logo-mark {
        width: 36px; height: 36px;
        border-radius: 10px;
        background: linear-gradient(135deg, var(--chart-1), var(--chart-2));
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 2px 8px var(--glow-primary), inset 0 1px 0 rgba(255,255,255,0.15);
        transition: all 0.3s var(--qm-spring);
        position: relative;
        overflow: hidden;
    }
    .qm-ws-topbar .logo-mark::before {
        content: '';
        position: absolute; inset: 0;
        background: linear-gradient(180deg, rgba(255,255,255,0.15) 0%, transparent 50%);
        pointer-events: none;
    }
    .qm-ws-topbar .logo-mark:hover {
        transform: scale(1.08) rotate(-2deg);
        box-shadow: 0 4px 16px var(--glow-primary), 0 0 24px var(--glow-accent);
    }
    .qm-ws-topbar .logo-mark svg {
        width: 18px; height: 18px;
        fill: none; stroke: #fff; stroke-width: 2;
        stroke-linecap: round; stroke-linejoin: round;
        position: relative; z-index: 1;
    }
    .qm-ws-topbar .brand-text {
        font-size: 1rem; font-weight: 650;
        color: var(--foreground);
        letter-spacing: -0.4px;
    }
    .qm-ws-topbar .brand-sub {
        font-size: 0.7rem; font-weight: 450;
        color: var(--qm-text-tertiary);
        letter-spacing: 0.3px;
        margin-left: 8px;
    }

    /* ── Workspace query card ── */
    .qm-query-card {
        background: var(--card);
        border: 0.5px solid var(--border);
        border-radius: var(--radius);
        padding: 1.5rem;
        margin-bottom: 1rem;
        animation: fadeSlideUp 0.45s var(--qm-spring-soft) both;
        position: relative;
        overflow: hidden;
    }
    .qm-query-card::before {
        content: '';
        position: absolute; top: 0; left: 0; right: 0;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(0,122,255,0.12), transparent);
    }
    .qm-query-card .card-label {
        font-size: 0.62rem; font-weight: 650;
        letter-spacing: 1.5px; text-transform: uppercase;
        color: var(--chart-1);
        margin-bottom: 0.75rem;
        display: flex; align-items: center; gap: 6px;
    }
    .qm-query-card .card-label::before {
        content: '';
        width: 4px; height: 4px;
        border-radius: 50%;
        background: var(--chart-1);
        box-shadow: 0 0 6px var(--glow-primary);
    }

    /* ── Result panel ── */
    .qm-result-panel {
        background: linear-gradient(180deg, var(--card) 0%, rgba(22,22,26,0.6) 100%);
        border: 0.5px solid var(--border);
        border-radius: var(--radius);
        padding: 1.5rem;
        margin: 1rem 0;
        animation: scaleIn 0.4s var(--qm-spring-soft) both;
        position: relative;
    }
    .qm-result-panel::before {
        content: '';
        position: absolute; top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--chart-1), var(--chart-2), var(--chart-3));
        border-radius: var(--radius) var(--radius) 0 0;
        opacity: 0.6;
    }

    /* ── Metrics cards ── */
    .qm-metrics-row {
        display: flex; gap: 0.75rem;
        margin: 1rem 0;
        animation: fadeSlideUp 0.4s 0.15s var(--qm-spring-soft) both;
    }
    .qm-metric-card {
        flex: 1;
        background: var(--surface-elevated);
        border: 0.5px solid var(--border);
        border-radius: var(--radius);
        padding: 0.85rem 1rem;
        text-align: center;
        transition: all 0.25s var(--qm-spring-soft);
    }
    .qm-metric-card:hover {
        border-color: var(--qm-border-hover);
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .qm-metric-card .metric-val {
        font-family: var(--qm-font);
        font-size: 1.1rem; font-weight: 650;
        color: var(--foreground);
        letter-spacing: -0.5px;
    }
    .qm-metric-card .metric-label {
        font-family: var(--qm-font);
        font-size: 0.62rem; font-weight: 550;
        letter-spacing: 1px; text-transform: uppercase;
        color: var(--qm-text-tertiary);
        margin-top: 2px;
    }
    .qm-metric-card:nth-child(1) .metric-val { color: var(--chart-1); }
    .qm-metric-card:nth-child(2) .metric-val { color: var(--chart-3); }
    .qm-metric-card:nth-child(3) .metric-val { color: var(--chart-2); }
    .qm-metric-card:nth-child(4) .metric-val { color: var(--chart-4); }

    /* ── Feedback buttons ── */
    .qm-feedback-good:hover { border-color: rgba(48, 209, 88, 0.2) !important; }
    .qm-feedback-bad:hover { border-color: rgba(255, 59, 48, 0.2) !important; }

    /* ── Sidebar logo ── */
    .qm-sidebar-logo {
        display: flex; align-items: center; gap: 10px;
        padding: 0.25rem 0 0.75rem 0;
        animation: fadeIn 0.4s var(--qm-spring-soft) both;
    }
    .qm-sidebar-logo .logo-mark {
        width: 28px; height: 28px;
        border-radius: 8px;
        background: linear-gradient(135deg, var(--chart-1), var(--chart-2));
        display: flex; align-items: center; justify-content: center;
        box-shadow: 0 1px 4px var(--glow-primary);
        position: relative; overflow: hidden;
    }
    .qm-sidebar-logo .logo-mark::before {
        content: '';
        position: absolute; inset: 0;
        background: linear-gradient(180deg, rgba(255,255,255,0.15) 0%, transparent 50%);
    }
    .qm-sidebar-logo .logo-mark svg {
        width: 14px; height: 14px;
        fill: none; stroke: #fff; stroke-width: 2.2;
        stroke-linecap: round; stroke-linejoin: round;
        position: relative; z-index: 1;
    }
    .qm-sidebar-logo .logo-text {
        font-size: 0.82rem; font-weight: 620;
        color: var(--foreground);
        letter-spacing: -0.3px;
    }

    /* ── Dividers ── */
    hr {
        border: none;
        border-top: 0.5px solid var(--qm-border);
        margin: 1.75rem 0;
    }

    /* ── Responsive ── */
    @media (max-width: 768px) {
        .qm-landing-hero h1 { font-size: 2.4rem; letter-spacing: -1.2px; }
        .qm-landing-hero p { font-size: 0.95rem; }
        .qm-features { grid-template-columns: 1fr; }
        .qm-security-grid { grid-template-columns: 1fr; }
        .qm-landing-nav { padding: 0.75rem 1.25rem; }
        .qm-landing-nav .nav-links { gap: 1rem; }
        .qm-landing-nav .nav-links a { font-size: 0.72rem; }
        .qm-landing-hero { padding: 4rem 1.5rem 3rem 1.5rem; }
    }
    @media (max-width: 480px) {
        .qm-landing-hero h1 { font-size: 1.8rem; }
        .qm-landing-nav .nav-links { display: none; }
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
            <div class="brand-icon" style="background: linear-gradient(135deg, var(--chart-1), var(--chart-2)); position: relative; overflow: hidden;">
                <div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(255,255,255,0.15) 0%,transparent 50%);pointer-events:none;"></div>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="position:relative;z-index:1">
                    <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
                    <path d="M8 11h6"/><path d="M11 8v6"/>
                </svg>
            </div>
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

    # SVG logo icon (search + plus = query creation)
    _LOGO_SVG = '''<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M8 11h6"/><path d="M11 8v6"/></svg>'''
    _LOGO_SVG_SM = '''<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M8 11h6"/><path d="M11 8v6"/></svg>'''

    # ── Workspace header ──
    hdr_left, hdr_right = st.columns([3, 1])
    with hdr_left:
        st.markdown(f"""
        <div class="qm-ws-topbar">
            <div class="brand">
                <div class="logo-mark">{_LOGO_SVG}</div>
                <span class="brand-text">QueryMind</span>
                <span class="brand-sub">Workspace</span>
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
        # Logo
        st.markdown(f"""
        <div class="qm-sidebar-logo">
            <div class="logo-mark">{_LOGO_SVG_SM}</div>
            <span class="logo-text">QueryMind</span>
        </div>
        """, unsafe_allow_html=True)

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

    # ── Query input (card) ──
    st.markdown("""
    <div class="qm-query-card">
        <div class="card-label">Ask a question</div>
    </div>
    """, unsafe_allow_html=True)
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

        # Result panel with gradient top border
        st.markdown('<div class="qm-result-panel"><div class="qm-label">Generated SQL</div></div>', unsafe_allow_html=True)
        st.code(result["final_sql"], language="sql")

        # Metric cards
        metric_cards = f"""
        <div class="qm-metrics-row">
            <div class="qm-metric-card">
                <div class="metric-val">{result["runtime_ms"]:.0f}ms</div>
                <div class="metric-label">Runtime</div>
            </div>
            <div class="qm-metric-card">
                <div class="metric-val">{result["row_count"]}</div>
                <div class="metric-label">Rows</div>
            </div>"""
        if result.get("explain_summary"):
            metric_cards += f"""
            <div class="qm-metric-card">
                <div class="metric-val">{result["explain_summary"]["total_cost"]:.0f}</div>
                <div class="metric-label">Cost</div>
            </div>
            <div class="qm-metric-card">
                <div class="metric-val">{result["explain_summary"]["estimated_rows"]:,}</div>
                <div class="metric-label">Est. Rows</div>
            </div>"""
        metric_cards += "</div>"
        st.markdown(metric_cards, unsafe_allow_html=True)

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
