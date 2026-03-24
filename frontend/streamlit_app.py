"""QueryMind Streamlit UI — Clean, minimal NL-to-SQL interface."""

import asyncio
import uuid

import pandas as pd
import streamlit as st

# Persistent user ID — stable across sessions via query param or default
# Users can bookmark ?user=myname to keep their identity (and feedback history)
_user_param = st.query_params.get("user")
if _user_param:
    # Deterministic UUID from the username so it's always the same
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

# --- Custom CSS for a clean, modern look ---
st.markdown("""
<style>
    /* Hide default Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Overall spacing */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 800px;
    }

    /* Brand header */
    .qm-header {
        text-align: center;
        padding: 1.5rem 0 0.5rem 0;
    }
    .qm-header h1 {
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        margin-bottom: 0.25rem;
        color: var(--text-color);
    }
    .qm-header p {
        font-size: 0.95rem;
        opacity: 0.55;
        margin: 0;
    }

    /* Card style container */
    .qm-card {
        border: 1px solid rgba(128,128,128,0.15);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.25rem;
        background: var(--secondary-background-color);
    }

    /* Result SQL block */
    .qm-sql-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        opacity: 0.5;
        margin-bottom: 0.25rem;
        font-weight: 600;
    }

    /* Metrics row */
    .qm-metrics {
        display: flex;
        gap: 1.5rem;
        margin: 0.75rem 0;
    }
    .qm-metric {
        font-size: 0.8rem;
        opacity: 0.6;
    }
    .qm-metric strong {
        opacity: 1;
        color: var(--text-color);
    }

    /* Subtle divider */
    hr {
        border: none;
        border-top: 1px solid rgba(128,128,128,0.1);
        margin: 1.5rem 0;
    }

    /* Status pill in sidebar */
    .qm-status {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.8rem;
        padding: 4px 10px;
        border-radius: 20px;
        background: rgba(76, 175, 80, 0.1);
        color: #4caf50;
        font-weight: 500;
    }
    .qm-status.offline {
        background: rgba(244, 67, 54, 0.1);
        color: #f44336;
    }

    /* Tighter textarea */
    .stTextArea textarea {
        border-radius: 8px !important;
    }

    /* Button styling */
    .stButton > button[kind="primary"] {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown("""
<div class="qm-header">
    <h1>QueryMind</h1>
    <p>Ask questions about your data in plain English</p>
</div>
""", unsafe_allow_html=True)

# --- Sidebar: minimal status + connections + history ---
with st.sidebar:
    # Status
    try:
        health = asyncio.run(health_check())
        if health["status"] == "ok":
            st.markdown(
                '<div class="qm-status">Connected</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<div class="qm-status offline">DB: {health["database"]}</div>',
                unsafe_allow_html=True,
            )
    except Exception:
        st.markdown(
            '<div class="qm-status offline">Backend offline</div>',
            unsafe_allow_html=True,
        )

    # User identity — set a name to persist feedback across sessions
    st.caption("USER")
    current_user = _user_param or ""
    new_user = st.text_input(
        "Username",
        value=current_user,
        key="username_input",
        placeholder="Enter a name to keep your history",
        label_visibility="collapsed",
    )
    if new_user and new_user != current_user:
        st.query_params["user"] = new_user
        st.rerun()
    if current_user:
        st.caption(f"Signed in as **{current_user}**")

    st.markdown("---")

    # Connection selector
    st.caption("CONNECTION")
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
        st.info("No connections. Add one below.")

    with st.expander("Manage connections", expanded=False):
        new_name = st.text_input("Name", key="new_conn_name", placeholder="my_database")
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
        st.caption(f"TABLES ({len(existing_tables)})")
        for t in existing_tables:
            st.markdown(
                f"<span style='font-size:0.85rem'>`{t['table_name']}` "
                f"<span style='opacity:0.5'>({t['column_count']} cols)</span></span>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # History
    st.caption("HISTORY")
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


# --- Main: Unified input area ---
# Query input
nl_query = st.text_area(
    "What would you like to know?",
    placeholder="e.g., Show the top 10 customers by total spend last quarter",
    height=120,
    label_visibility="collapsed",
)

# Data input — paste table/SQL and file upload in a compact section
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

    # Detect if input looks like SQL
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

    # File upload
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

# --- Results ---
result = st.session_state.get("last_result")
if result and result["status"] == "success":
    st.markdown("---")

    # SQL
    st.markdown('<div class="qm-sql-label">Generated SQL</div>', unsafe_allow_html=True)
    st.code(result["final_sql"], language="sql")

    # Metrics row
    metrics_parts = [f"**{result['runtime_ms']:.0f}ms** runtime"]
    metrics_parts.append(f"**{result['row_count']}** rows")
    if result.get("explain_summary"):
        metrics_parts.append(f"cost **{result['explain_summary']['total_cost']:.0f}**")
        metrics_parts.append(f"est. **{result['explain_summary']['estimated_rows']:,}** rows")
    st.caption(" &nbsp;|&nbsp; ".join(metrics_parts))

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

    # Feedback — compact inline
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
