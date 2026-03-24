"""QueryMind — Premium NL-to-SQL interface."""

import asyncio
import uuid

import pandas as pd
import streamlit as st

# Persistent user ID — stable across sessions via query param
_user_param = st.query_params.get("user")
if _user_param:
    stable_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, _user_param))
    st.session_state["user_id"] = stable_id
elif "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())

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

st.set_page_config(page_title="QueryMind", page_icon="Q", layout="centered")

# ──────────────────────────────────────────────────────────────
# Premium Design System — "Syntactic Slate"
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Import premium font ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Hide Streamlit chrome ── */
    #MainMenu, footer, header { visibility: hidden; }
    .stDeployButton { display: none; }

    /* ── Global foundation ── */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'SF Pro Display', sans-serif;
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
    }

    [data-testid="stAppViewContainer"] {
        background: #121214;
    }

    .block-container {
        padding-top: 3rem;
        padding-bottom: 4rem;
        max-width: 780px;
    }

    /* ── Entrance animations ── */
    @keyframes fadeSlideUp {
        from { opacity: 0; transform: translateY(16px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeIn {
        from { opacity: 0; }
        to { opacity: 1; }
    }
    @keyframes subtleGlow {
        0%, 100% { box-shadow: 0 0 20px rgba(138, 143, 152, 0.03); }
        50% { box-shadow: 0 0 30px rgba(138, 143, 152, 0.06); }
    }

    .block-container > div {
        animation: fadeSlideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    }

    /* ── Hero / Brand ── */
    .qm-hero {
        text-align: center;
        padding: 2.5rem 0 2rem 0;
        animation: fadeSlideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
    }
    .qm-logo {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 44px;
        height: 44px;
        border-radius: 12px;
        background: linear-gradient(135deg, #2a2a2e 0%, #1c1c1f 100%);
        border: 0.5px solid rgba(228, 228, 231, 0.08);
        margin-bottom: 1.25rem;
        font-size: 1.1rem;
        font-weight: 600;
        color: #8a8f98;
        letter-spacing: -0.5px;
        box-shadow:
            0 1px 3px rgba(0,0,0,0.3),
            inset 0 1px 0 rgba(255,255,255,0.03);
    }
    .qm-hero h1 {
        font-size: 1.85rem;
        font-weight: 700;
        letter-spacing: -0.8px;
        color: #e4e4e7;
        margin: 0 0 0.4rem 0;
        line-height: 1.15;
    }
    .qm-hero p {
        font-size: 0.88rem;
        font-weight: 400;
        color: rgba(228, 228, 231, 0.38);
        margin: 0;
        letter-spacing: 0.2px;
    }

    /* ── Subtle dividers ── */
    hr {
        border: none;
        border-top: 0.5px solid rgba(228, 228, 231, 0.06);
        margin: 1.75rem 0;
    }

    /* ── Input surfaces ── */
    .stTextArea textarea,
    .stTextInput input {
        background: #1c1c1f !important;
        border: 0.5px solid rgba(228, 228, 231, 0.08) !important;
        border-radius: 10px !important;
        color: #e4e4e7 !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.9rem !important;
        padding: 0.85rem 1rem !important;
        transition: border-color 0.25s cubic-bezier(0.16, 1, 0.3, 1),
                    box-shadow 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
        caret-color: #8a8f98 !important;
    }
    .stTextArea textarea:focus,
    .stTextInput input:focus {
        border-color: rgba(138, 143, 152, 0.3) !important;
        box-shadow: 0 0 0 3px rgba(138, 143, 152, 0.06),
                    0 1px 2px rgba(0,0,0,0.2) !important;
        outline: none !important;
    }
    .stTextArea textarea::placeholder,
    .stTextInput input::placeholder {
        color: rgba(228, 228, 231, 0.2) !important;
        font-weight: 400 !important;
    }

    /* ── Primary button — luxe tactile ── */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(180deg, #2a2a2e 0%, #232326 100%) !important;
        border: 0.5px solid rgba(228, 228, 231, 0.1) !important;
        border-radius: 10px !important;
        color: #e4e4e7 !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.88rem !important;
        letter-spacing: 0.1px !important;
        padding: 0.65rem 1.5rem !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
        box-shadow:
            0 1px 2px rgba(0,0,0,0.25),
            inset 0 1px 0 rgba(255,255,255,0.04) !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(180deg, #303034 0%, #28282c 100%) !important;
        border-color: rgba(228, 228, 231, 0.15) !important;
        box-shadow:
            0 2px 8px rgba(0,0,0,0.3),
            inset 0 1px 0 rgba(255,255,255,0.05) !important;
        transform: translateY(-0.5px) !important;
    }
    .stButton > button[kind="primary"]:active,
    .stButton > button[data-testid="stBaseButton-primary"]:active {
        transform: scale(0.975) translateY(0) !important;
        box-shadow: 0 0 0 rgba(0,0,0,0.2) !important;
    }

    /* ── Secondary / default buttons ── */
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="stBaseButton-secondary"],
    .stButton > button:not([kind]) {
        background: transparent !important;
        border: 0.5px solid rgba(228, 228, 231, 0.08) !important;
        border-radius: 10px !important;
        color: rgba(228, 228, 231, 0.6) !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.82rem !important;
        padding: 0.55rem 1.25rem !important;
        transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="stBaseButton-secondary"]:hover,
    .stButton > button:not([kind]):hover {
        background: rgba(228, 228, 231, 0.03) !important;
        border-color: rgba(228, 228, 231, 0.12) !important;
        color: #e4e4e7 !important;
    }
    .stButton > button[kind="secondary"]:active,
    .stButton > button[data-testid="stBaseButton-secondary"]:active,
    .stButton > button:not([kind]):active {
        transform: scale(0.97) !important;
    }

    /* ── Expander — glass panel ── */
    .streamlit-expanderHeader {
        background: rgba(28, 28, 31, 0.6) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 0.5px solid rgba(228, 228, 231, 0.06) !important;
        border-radius: 10px !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        color: rgba(228, 228, 231, 0.55) !important;
        letter-spacing: 0.2px !important;
        padding: 0.7rem 1rem !important;
        transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1) !important;
    }
    .streamlit-expanderHeader:hover {
        border-color: rgba(228, 228, 231, 0.1) !important;
        color: rgba(228, 228, 231, 0.75) !important;
        background: rgba(28, 28, 31, 0.8) !important;
    }
    [data-testid="stExpander"] {
        border: 0.5px solid rgba(228, 228, 231, 0.04) !important;
        border-radius: 10px !important;
        overflow: hidden;
    }
    [data-testid="stExpander"] details {
        border: none !important;
    }

    /* ── Code blocks — refined ── */
    .stCodeBlock, pre, code {
        border-radius: 10px !important;
    }
    [data-testid="stCodeBlock"] {
        border: 0.5px solid rgba(228, 228, 231, 0.05) !important;
        border-radius: 10px !important;
        overflow: hidden;
    }

    /* ── Dataframe — premium table ── */
    [data-testid="stDataFrame"] {
        border: 0.5px solid rgba(228, 228, 231, 0.06) !important;
        border-radius: 10px !important;
        overflow: hidden;
        animation: fadeSlideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
    }

    /* ── Sidebar — glass panel ── */
    [data-testid="stSidebar"] {
        background: rgba(18, 18, 20, 0.85) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-right: 0.5px solid rgba(228, 228, 231, 0.05) !important;
    }
    [data-testid="stSidebar"] .block-container {
        padding-top: 1.5rem;
    }

    /* ── Status pill ── */
    .qm-status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.72rem;
        font-weight: 500;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        padding: 5px 12px;
        border-radius: 20px;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .qm-status-pill.online {
        background: rgba(74, 222, 128, 0.08);
        color: rgba(74, 222, 128, 0.7);
        border: 0.5px solid rgba(74, 222, 128, 0.1);
    }
    .qm-status-pill.offline {
        background: rgba(248, 113, 113, 0.08);
        color: rgba(248, 113, 113, 0.7);
        border: 0.5px solid rgba(248, 113, 113, 0.1);
    }

    /* ── Sidebar section labels ── */
    .qm-section-label {
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.65rem;
        font-weight: 600;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: rgba(228, 228, 231, 0.25);
        margin: 1rem 0 0.5rem 0;
    }

    /* ── Table list items in sidebar ── */
    .qm-table-item {
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.8rem;
        color: rgba(228, 228, 231, 0.55);
        padding: 4px 0;
        transition: color 0.2s ease;
    }
    .qm-table-item code {
        font-size: 0.78rem;
        color: rgba(228, 228, 231, 0.7);
        background: rgba(228, 228, 231, 0.04);
        padding: 2px 6px;
        border-radius: 4px;
        border: 0.5px solid rgba(228, 228, 231, 0.06);
    }
    .qm-table-item .cols {
        color: rgba(228, 228, 231, 0.25);
        font-size: 0.72rem;
        margin-left: 4px;
    }

    /* ── Result section labels ── */
    .qm-label {
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.65rem;
        font-weight: 600;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        color: rgba(228, 228, 231, 0.25);
        margin-bottom: 0.6rem;
    }

    /* ── Metrics strip ── */
    .qm-metrics-strip {
        display: flex;
        gap: 1.25rem;
        padding: 0.6rem 0;
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.78rem;
        color: rgba(228, 228, 231, 0.3);
        animation: fadeIn 0.5s 0.2s both;
    }
    .qm-metrics-strip .val {
        color: rgba(228, 228, 231, 0.6);
        font-weight: 500;
    }

    /* ── Result card ── */
    .qm-result-card {
        background: linear-gradient(180deg, rgba(28, 28, 31, 0.5) 0%, rgba(28, 28, 31, 0.3) 100%);
        border: 0.5px solid rgba(228, 228, 231, 0.05);
        border-radius: 14px;
        padding: 1.5rem;
        margin: 1rem 0;
        animation: fadeSlideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
        box-shadow: 0 4px 24px rgba(0,0,0,0.15);
    }

    /* ── Feedback buttons ── */
    .qm-feedback-row {
        display: flex;
        gap: 0.5rem;
        margin-top: 1rem;
    }

    /* ── Selectbox refinement ── */
    [data-testid="stSelectbox"] > div > div {
        background: #1c1c1f !important;
        border: 0.5px solid rgba(228, 228, 231, 0.08) !important;
        border-radius: 10px !important;
    }

    /* ── File uploader ── */
    [data-testid="stFileUploader"] {
        border: 0.5px dashed rgba(228, 228, 231, 0.08) !important;
        border-radius: 10px !important;
        transition: border-color 0.25s ease !important;
    }
    [data-testid="stFileUploader"]:hover {
        border-color: rgba(228, 228, 231, 0.15) !important;
    }

    /* ── Spinner ── */
    .stSpinner > div {
        border-color: rgba(138, 143, 152, 0.3) !important;
        border-top-color: #8a8f98 !important;
    }

    /* ── Alert boxes — refined ── */
    [data-testid="stAlert"] {
        border-radius: 10px !important;
        border-width: 0.5px !important;
        font-size: 0.85rem !important;
    }

    /* ── Progress bar ── */
    .stProgress > div > div {
        background: rgba(138, 143, 152, 0.15) !important;
        border-radius: 4px !important;
    }
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #8a8f98, #6b6f77) !important;
        border-radius: 4px !important;
    }

    /* ── Toast ── */
    [data-testid="stToast"] {
        backdrop-filter: blur(12px) !important;
        border: 0.5px solid rgba(228, 228, 231, 0.06) !important;
        border-radius: 10px !important;
    }

    /* ── Chart styling ── */
    [data-testid="stVegaLiteChart"] {
        border: 0.5px solid rgba(228, 228, 231, 0.04) !important;
        border-radius: 10px !important;
        overflow: hidden;
        padding: 0.5rem;
    }

    /* ── Caption / small text refinement ── */
    .stCaption, [data-testid="stCaption"] {
        font-family: 'Inter', -apple-system, sans-serif !important;
        letter-spacing: 0.1px !important;
    }

    /* ── User signed-in badge ── */
    .qm-user-badge {
        font-family: 'Inter', -apple-system, sans-serif;
        font-size: 0.72rem;
        font-weight: 500;
        color: rgba(228, 228, 231, 0.35);
        padding: 3px 0;
        letter-spacing: 0.2px;
    }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# Hero
# ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="qm-hero">
    <div class="qm-logo">Q</div>
    <h1>QueryMind</h1>
    <p>Ask questions about your data in plain English</p>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────
# Main — Query Input
# ──────────────────────────────────────────────────────────────
nl_query = st.text_area(
    "What would you like to know?",
    placeholder="e.g., Show the top 10 customers by total spend last quarter",
    height=120,
    label_visibility="collapsed",
)

# Data import — collapsible
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

# Run button
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

# ──────────────────────────────────────────────────────────────
# Results
# ──────────────────────────────────────────────────────────────
result = st.session_state.get("last_result")
if result and result["status"] == "success":
    st.markdown("---")

    # SQL
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

    # Data table
    if result["rows"]:
        df = pd.DataFrame(result["rows"], columns=result["columns"])
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Chart
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols and len(df) > 1:
            non_numeric = [c for c in df.columns if c not in numeric_cols]
            if non_numeric:
                chart_df = df.set_index(non_numeric[0])[numeric_cols]
                st.bar_chart(chart_df)
            else:
                st.bar_chart(df[numeric_cols])

    # Validation
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

    # Self-correction attempts
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
