"""QueryMind Streamlit UI — NL-to-SQL with feedback and history."""

import asyncio
import uuid

import pandas as pd
import streamlit as st

# Generate a persistent user ID per browser session
if "user_id" not in st.session_state:
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


st.set_page_config(page_title="QueryMind", page_icon="🔍", layout="wide")
st.title("QueryMind — Natural Language to SQL")

# --- Sidebar: Health, Connections & History ---
with st.sidebar:
    st.header("Status")
    try:
        health = asyncio.run(health_check())
        if health["status"] == "ok":
            st.success(f"Backend: {health['status']} | DB: {health['database']}")
        else:
            st.warning(f"Backend: {health['status']} | DB: {health['database']}")
    except Exception as e:
        st.error(f"Backend unreachable: {e}")

    # --- Connection selector ---
    st.header("Target Connection")
    try:
        connections = asyncio.run(get_connections())
    except Exception:
        connections = []

    if connections:
        conn_names = [c["name"] for c in connections]
        selected_idx = st.selectbox(
            "Select connection",
            range(len(conn_names)),
            format_func=lambda i: conn_names[i],
            key="conn_select",
        )
        selected_connection = connections[selected_idx]
        st.caption(f"ID: {selected_connection['id']}")
    else:
        selected_connection = None
        st.info("No connections configured. Add one below or queries will use the default.")

    # --- Add connection ---
    with st.expander("Add Connection"):
        new_name = st.text_input("Connection name", key="new_conn_name")
        new_url = st.text_input("Database URL", key="new_conn_url", type="password")
        if st.button("Add", key="add_conn_btn"):
            if new_name and new_url:
                try:
                    asyncio.run(create_connection(new_name, new_url))
                    st.success(f"Connection '{new_name}' added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")
            else:
                st.warning("Name and URL are required.")

    # --- Remove connection ---
    if connections and len(connections) > 1:
        with st.expander("Remove Connection"):
            rm_names = [c["name"] for c in connections]
            rm_idx = st.selectbox("Select to remove", range(len(rm_names)), format_func=lambda i: rm_names[i], key="rm_conn")
            if st.button("Remove", key="rm_conn_btn"):
                try:
                    asyncio.run(delete_connection(connections[rm_idx]["id"]))
                    st.success(f"Connection '{rm_names[rm_idx]}' removed!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed: {e}")

    # --- History ---
    st.header("Query History")
    status_filter = st.selectbox("Filter by status", [None, "success", "error", "blocked"])
    if st.button("Load History"):
        try:
            history = asyncio.run(get_history(status=status_filter, user_id=st.session_state["user_id"]))
            for item in history["items"]:
                with st.expander(f"{item['nl_query'][:60]}... ({item['status']})"):
                    st.text(f"ID: {item['id']}")
                    st.text(f"Status: {item['status']}")
                    st.text(f"Rows: {item['row_count']}")
                    st.text(f"Time: {item['runtime_ms']:.0f}ms" if item["runtime_ms"] else "")
                    if item["final_sql"]:
                        st.code(item["final_sql"], language="sql")
        except Exception as e:
            st.error(f"Failed to load history: {e}")

# --- Main: Data Setup ---
st.subheader("1. Provide Your Data")
st.caption("Upload multiple tables, then ask questions across all of them.")

# Show existing tables
conn_id = selected_connection["id"] if selected_connection else None
try:
    existing_tables = asyncio.run(get_tables(connection_id=conn_id))
    if existing_tables:
        with st.expander(f"Tables in database ({len(existing_tables)})", expanded=False):
            for t in existing_tables:
                st.text(f"  {t['table_name']} ({t['column_count']} columns)")
except Exception:
    existing_tables = []

paste_tab, sql_tab, upload_tab = st.tabs(["Paste Table", "Write SQL", "Upload Files"])

with paste_tab:
    table_name = st.text_input(
        "Table name:",
        value="user_table",
        key="table_name_input",
    )
    table_data = st.text_area(
        "Paste your table (markdown, CSV, or TSV):",
        height=250,
        key="table_data_input",
        placeholder="""| Date       | Widget_Type | Daily_Production |
| ---------- | ----------- | ---------------- |
| 2019-12-01 | A           | 30               |
| 2019-12-02 | A           | 30               |
| 2019-12-03 | A           | 15               |

Or CSV:
Date,Widget_Type,Daily_Production
2019-12-01,A,30
2019-12-02,A,30""",
    )
    if st.button("Import Table", type="secondary", key="import_btn"):
        if table_data and table_data.strip():
            conn_id = selected_connection["id"] if selected_connection else None
            with st.spinner("Parsing and importing table..."):
                try:
                    result = asyncio.run(
                        import_table(table_data.strip(), table_name.strip(), connection_id=conn_id)
                    )
                    if result["status"] == "success":
                        st.success(
                            f"Table **{result['table_name']}** created with "
                            f"{len(result['columns'])} columns and ~{result['row_count']} rows!"
                        )
                        with st.expander("Generated SQL"):
                            st.code(result["generated_sql"], language="sql")
                    else:
                        st.error(f"Import failed: {result.get('error')}")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.warning("Please paste your table data first.")

with sql_tab:
    schema_ddl = st.text_area(
        "DDL + Data (CREATE TABLE, INSERT INTO):",
        height=250,
        key="schema_ddl_input",
        placeholder="""CREATE TABLE widget_production (
    date DATE,
    widget_type VARCHAR(10),
    daily_production INTEGER
);

INSERT INTO widget_production VALUES
('2019-12-01', 'A', 30),
('2019-12-02', 'A', 30);""",
    )
    if st.button("Execute SQL", type="secondary", key="setup_btn"):
        if schema_ddl and schema_ddl.strip():
            conn_id = selected_connection["id"] if selected_connection else None
            with st.spinner("Executing DDL..."):
                try:
                    result = asyncio.run(setup_schema(schema_ddl.strip(), connection_id=conn_id))
                    if result["status"] == "success":
                        st.success(f"Done! {result['statements_executed']} statement(s) executed.")
                        with st.expander("Executed statements"):
                            for s in result["statements"]:
                                st.code(s, language="sql")
                    else:
                        st.error(f"Failed: {result.get('error')}")
                except Exception as e:
                    st.error(f"Error: {e}")
        else:
            st.warning("Please provide SQL statements first.")

with upload_tab:
    uploaded_files = st.file_uploader(
        "Upload .sql, .csv, or .tsv files (multiple allowed)",
        type=["sql", "txt", "csv", "tsv"],
        key="file_upload",
        accept_multiple_files=True,
    )
    if uploaded_files:
        # Cache file contents
        cached_files = []
        for uf in uploaded_files:
            cache_key = f"file_cache_{uf.name}_{uf.size}"
            if cache_key not in st.session_state:
                st.session_state[cache_key] = uf.read().decode("utf-8")
            cached_files.append((uf.name, st.session_state[cache_key]))

        # Show preview for each file
        for fname, content in cached_files:
            lines = content.strip().split("\n")
            is_sql = fname.endswith(".sql")
            table_name = fname.rsplit(".", 1)[0].replace(" ", "_").replace("-", "_").lower()
            with st.expander(f"{fname} — ~{len(lines) - 1} rows | {len(content):,} chars"):
                st.code(content[:1000], language="sql" if is_sql else "text")

        if st.button("Import All Files", type="secondary", key="upload_import_btn"):
            conn_id = selected_connection["id"] if selected_connection else None
            progress = st.progress(0, text="Importing...")
            total = len(cached_files)
            for idx, (fname, content) in enumerate(cached_files):
                is_sql = fname.endswith(".sql")
                table_name = fname.rsplit(".", 1)[0].replace(" ", "_").replace("-", "_").lower()
                progress.progress((idx) / total, text=f"Importing {fname}...")
                try:
                    if is_sql:
                        result = asyncio.run(setup_schema(content, connection_id=conn_id))
                        if result["status"] == "success":
                            st.success(f"{fname}: {result['statements_executed']} statement(s) executed.")
                        else:
                            st.error(f"{fname}: {result.get('error')}")
                    else:
                        result = asyncio.run(
                            import_table(content, table_name, connection_id=conn_id)
                        )
                        if result["status"] == "success":
                            st.success(
                                f"{fname} → **{result['table_name']}** "
                                f"({len(result['columns'])} cols, ~{result['row_count']} rows)"
                            )
                        else:
                            st.error(f"{fname}: {result.get('error')}")
                except Exception as e:
                    st.error(f"{fname}: {e}")
            progress.progress(1.0, text="Done!")
            st.rerun()

st.divider()

# --- Main: Query Input ---
st.subheader("2. Ask a Question")
nl_query = st.text_area(
    "Enter your question in natural language:",
    placeholder="e.g., How many employees are in each department?",
    height=100,
)

col1, col2 = st.columns([1, 4])
with col1:
    run_button = st.button("Run Query", type="primary", use_container_width=True)

if run_button and nl_query.strip():
    conn_id = selected_connection["id"] if selected_connection else None

    with st.spinner("Generating and executing SQL..."):
        try:
            result = asyncio.run(
                run_query(
                    nl_query.strip(),
                    user_id=st.session_state["user_id"],
                    connection_id=conn_id,
                )
            )

            if result["status"] == "success":
                # --- SQL Display ---
                st.subheader("Generated SQL")
                st.code(result["final_sql"], language="sql")

                # --- Results Table ---
                if result["rows"]:
                    st.subheader(f"Results ({result['row_count']} rows)")
                    df = pd.DataFrame(result["rows"], columns=result["columns"])
                    st.dataframe(df, use_container_width=True)

                    # --- Chart for numeric columns ---
                    numeric_cols = df.select_dtypes(include="number").columns.tolist()
                    if numeric_cols and len(df) > 1:
                        st.subheader("Chart")
                        non_numeric = [c for c in df.columns if c not in numeric_cols]
                        if non_numeric:
                            chart_df = df.set_index(non_numeric[0])[numeric_cols]
                            st.bar_chart(chart_df)
                        else:
                            st.bar_chart(df[numeric_cols])

                # --- Metrics ---
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                col_m1.metric("Runtime", f"{result['runtime_ms']:.0f}ms")
                col_m2.metric("Rows", result["row_count"])
                if result.get("explain_summary"):
                    col_m3.metric("EXPLAIN Cost", f"{result['explain_summary']['total_cost']:.0f}")
                    col_m4.metric("Est. Rows", f"{result['explain_summary']['estimated_rows']:,}")

                # --- Validation ---
                if result.get("validation_summary"):
                    vs = result["validation_summary"]
                    if vs["success"]:
                        st.success(
                            f"Validation passed: {vs['expectations_passed']}/{vs['expectations_evaluated']} expectations"
                        )
                    else:
                        st.warning(
                            f"Validation issues: {vs['expectations_passed']}/{vs['expectations_evaluated']} passed"
                        )
                        for detail in vs.get("details", []):
                            if not detail["success"]:
                                st.text(f"  Failed: {detail['expectation']}")

                # --- Attempted SQLs (debug) ---
                if len(result.get("attempted_sqls", [])) > 1:
                    with st.expander("Self-correction attempts"):
                        for i, sql in enumerate(result["attempted_sqls"]):
                            st.text(f"Attempt {i + 1}:")
                            st.code(sql, language="sql")

                # --- Feedback ---
                st.subheader("Feedback")
                st.session_state["last_query_id"] = result["query_id"]

                fcol1, fcol2 = st.columns(2)
                with fcol1:
                    if st.button("👍 Good result"):
                        asyncio.run(submit_feedback(result["query_id"], rating=5))
                        st.success("Thanks for your feedback!")
                with fcol2:
                    if st.button("👎 Bad result"):
                        st.session_state["show_correction"] = True

                if st.session_state.get("show_correction"):
                    corrected = st.text_area("Correct SQL (optional):", key="corrected_sql")
                    notes = st.text_input("Notes (optional):", key="feedback_notes")
                    if st.button("Submit Correction"):
                        asyncio.run(
                            submit_feedback(
                                result["query_id"],
                                rating=1,
                                corrected_sql=corrected or None,
                                notes=notes or None,
                            )
                        )
                        st.success("Correction saved — it will improve future queries!")
                        st.session_state["show_correction"] = False

            else:
                st.error(f"Query failed: {result.get('error', 'Unknown error')}")
                if result.get("attempted_sqls"):
                    with st.expander("Attempted SQL"):
                        for i, sql in enumerate(result["attempted_sqls"]):
                            st.text(f"Attempt {i + 1}:")
                            st.code(sql, language="sql")

        except Exception as e:
            st.error(f"Error: {e}")

elif run_button:
    st.warning("Please enter a question first.")
