
import os

# Use the regular Hugging Face transfer path when Xet's CAS endpoint is
# unavailable on the current network.
os.environ["HF_HUB_DISABLE_XET"] = "1"

import streamlit as st
from pathlib import Path
from app_backend import data_status, execute_readonly, load_schemas, load_pipeline_resources

# ---------- PAGE SETTINGS ----------
st.set_page_config(
    page_title="QueryClarify AI",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- FILE PATHS ----------
BASE_DIR = Path(__file__).parent
LOGO_PATH = BASE_DIR / "queryclarify_logo.png"

# ---------- COLOR PALETTE ----------
SLATE = "#738290"
DARK_SLATE = "#344B5E"
CREAM = "#F7F5EF"
SIDEBAR_GREEN = "#EAEFE5"
DIVIDER = "#E1E6ED"

# ---------- CUSTOM CSS ----------
st.markdown("""
<style>
    /* Main page background */
    .stApp {
        background-color: #F7F5EF;
        color: #344B5E;
    }

    /* Hide Streamlit's top header */
    header[data-testid="stHeader"] {
        display: none;
    }

    /* Hide top toolbar and Deploy controls */
    [data-testid="stToolbar"] {
        display: none;
    }

    /* Hide the top-right menu if still visible */
    [data-testid="stMainMenu"] {
        display: none;
    }

    /* Main content spacing */
    .block-container {
        max-width: 1250px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #EAEFE5;
        border-right: 1px solid #D5DED0;
    }

    [data-testid="stSidebar"] .block-container {
        padding-top: 1.5rem;
    }

    /* Main page heading */
    .eyebrow {
        display: block;
        color: #738290;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 2px;
        margin: 0 0 0.8rem 0;
    }

    .main-heading {
        display: block;
        color: #344B5E;
        font-size: 2.5rem;
        font-weight: 650;
        letter-spacing: -1px;
        line-height: 1.3;
        margin: 0 0 0.8rem 0;
        overflow-wrap: break-word;
    }

    .subtitle {
        display: block;
        color: #65717B;
        font-size: 1rem;
        line-height: 1.8;
        margin: 0 0 2rem 0;
        max-width: 850px;
    }

    /* Headings and column spacing */
    h2, h3 {
        color: #344B5E;
        line-height: 1.4 !important;
        letter-spacing: -0.3px;
    }

    div[data-testid="stHorizontalBlock"] {
        align-items: flex-start;
        gap: 2rem;
    }

    div[data-testid="stColumn"] {
        min-width: 0;
    }

    div[data-testid="stColumn"] h3 {
        margin-top: 0.3rem;
        margin-bottom: 1rem;
        line-height: 1.4 !important;
    }

    /* Question input */
    div[data-testid="stTextArea"] textarea {
        background-color: #FFFFFF;
        border: 1px solid #D5DDE4;
        border-radius: 10px;
        color: #344B5E;
        padding: 14px;
        font-size: 1rem;
        line-height: 1.6;
    }

    div[data-testid="stTextArea"] textarea:focus {
        border-color: #738290;
        box-shadow: 0 0 0 1px #738290;
    }

    /* Buttons */
    div.stButton > button[kind="primary"],
    div.stFormSubmitButton > button[kind="primary"] {
        background-color: #526B7D;
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        min-height: 44px;
        font-weight: 600;
        padding: 0.5rem 1.2rem;
        transition: background-color 0.2s ease;
    }

    div.stButton > button[kind="primary"]:hover,
    div.stFormSubmitButton > button[kind="primary"]:hover {
        background-color: #3F5667;
        color: #FFFFFF;
    }

    /* SQL output */
    [data-testid="stCodeBlock"] {
        border: 1px solid #D5DED0;
        border-radius: 8px;
    }

    /* Dividers */
    hr {
        border: none;
        border-top: 1px solid #E1E6ED;
        margin-top: 1.8rem;
        margin-bottom: 1.8rem;
    }

    /* Supporting text */
    .small-note {
        color: #738290;
        font-size: 0.85rem;
        line-height: 1.6;
    }

    .footer {
        color: #738290;
        text-align: center;
        font-size: 0.8rem;
        padding-top: 1.5rem;
    }

    /* Mobile adjustments */
    @media (max-width: 700px) {
        .block-container {
            padding-top: 1rem;
        }

        .main-heading {
            font-size: 2rem;
        }

        .subtitle {
            margin-bottom: 1.5rem;
        }
    }
</style>
""", unsafe_allow_html=True)


# ---------- SESSION STATE ----------
if "submitted" not in st.session_state:
    st.session_state["submitted"] = False

if "question" not in st.session_state:
    st.session_state["question"] = ""
if "pipeline_result" not in st.session_state:
    st.session_state["pipeline_result"] = None
if "clarification_state" not in st.session_state:
    st.session_state["clarification_state"] = None
if "clarification_answer" not in st.session_state:
    st.session_state["clarification_answer"] = ""
if "query_error" not in st.session_state:
    st.session_state["query_error"] = ""

DATA_DIR, DATA_ERROR = data_status()
SCHEMAS = load_schemas(DATA_DIR) if DATA_DIR else {}


# ---------- SIDEBAR ----------
with st.sidebar:

    # Display custom logo
    if LOGO_PATH.exists():
        st.image(
            str(LOGO_PATH),
            use_container_width=True
        )
    else:
        st.markdown("## QueryClarify AI")
        st.caption("Natural language to SQL")
        st.warning(
            "Logo not found. Save the image as "
            "'queryclarify_logo.png' beside app.py."
        )

    st.divider()

    st.markdown("**WORKSPACE**")

    if SCHEMAS:
        database = st.selectbox("Choose database", sorted(SCHEMAS))
    else:
        database = None
        st.caption("Configure QUERYCLARIFY_DATA_DIR to enable your databases.")

    st.divider()

    st.markdown("**HOW IT WORKS**")
    st.caption("01  Understand the question")
    st.caption("02  Clarify ambiguity")
    st.caption("03  Generate SQL")
    st.caption("04  Return query results")

   


# ---------- PAGE HEADER ----------
st.markdown(
    '<div class="eyebrow">'
    'INTELLIGENT DATA QUERYING'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="main-heading">'
    'Your data, in plain English.'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div class="subtitle">'
    'Ask a question naturally. Clarify your intent when needed, '
    'generate SQL, and explore your data.'
    '</div>',
    unsafe_allow_html=True
)


# ---------- INPUT + CLARIFICATION COLUMNS ----------
input_col, clarification_col = st.columns(
    [1.15, 0.85],
    gap="large"
)

with input_col:
    st.markdown("### Ask your question")

    with st.form("query_form"):
        question_input = st.text_area(
            "Question",
            value=st.session_state["question"],
            placeholder=(
                "e.g. Find the five highest-selling "
                "products this month..."
            ),
            height=155,
            label_visibility="collapsed"
        )

        submitted = st.form_submit_button(
            "Generate SQL  →",
            type="primary",
            use_container_width=True
        )

    st.markdown(
        '<div class="small-note">'
        'Use everyday language. Be as specific as possible.'
        '</div>',
        unsafe_allow_html=True
    )


# ---------- PIPELINE CONNECTION ----------
if DATA_ERROR:
    st.warning(DATA_ERROR)

@st.cache_resource(show_spinner=False)
def _load_resources(data_dir, llm_name, embedding_name):
    return load_pipeline_resources(
        data_dir, llm_name, embedding_name,
    )

LLM_NAME = os.getenv("QUERYCLARIFY_LLM_MODEL", "Qwen/Qwen2.5-3B-Instruct")
EMBEDDING_NAME = os.getenv("QUERYCLARIFY_EMBEDDING_MODEL", "all-MiniLM-L6-v2")

def get_resources():
    return _load_resources(str(DATA_DIR), LLM_NAME, EMBEDDING_NAME)

if submitted:
    st.session_state["query_error"] = ""
    st.session_state["pipeline_result"] = None
    st.session_state["clarification_state"] = None
    if not question_input.strip():
        st.session_state["query_error"] = "Please enter a question first."
    elif not database:
        st.session_state["query_error"] = "Add the Spider data folder before running a query."
    else:
        st.session_state["question"] = question_input.strip()
        st.session_state["submitted"] = True
        try:
            with st.spinner("Loading the models and analyzing your question…"):
                schemas, model, tokenizer, embedding_model, start_query, _ = get_resources()
                result = start_query(
                    question=question_input.strip(), db_id=database,
                    db=schemas[database], embedding_model=embedding_model,
                    model=model, tokenizer=tokenizer,
                )
            st.session_state["pipeline_result"] = result
            if result.get("status") == "clarification_required":
                st.session_state["clarification_state"] = result.get("state")
        except Exception as exc:
            st.session_state["query_error"] = str(exc)

if st.session_state.get("clarification_state"):
    clarification_state = st.session_state["clarification_state"]
    with clarification_col:
        st.info(clarification_state.get("pending_question", "Please clarify your request."))
        with st.form("clarification_form"):
            clarification_answer = st.text_input(
                "Your answer", key="clarification_answer",
                placeholder="Add the detail needed to build your query"
            )
            continue_clicked = st.form_submit_button("Continue →", type="primary")
    if continue_clicked:
        if not clarification_answer.strip():
            st.session_state["query_error"] = "Please answer the clarification question."
        else:
            st.session_state["query_error"] = ""
            try:
                with st.spinner("Generating SQL from your clarified question…"):
                    schemas, model, tokenizer, embedding_model, _, continue_query = get_resources()
                    result = continue_query(
                        state=clarification_state,
                        clarification_answer=clarification_answer,
                        db=schemas[database], embedding_model=embedding_model,
                        model=model, tokenizer=tokenizer,
                    )
                st.session_state["pipeline_result"] = result
                if result.get("status") != "clarification_required":
                    st.session_state["clarification_state"] = None
            except Exception as exc:
                st.session_state["query_error"] = str(exc)

result = st.session_state.get("pipeline_result") or {}
if st.session_state.get("query_error"):
    st.error(st.session_state["query_error"])
elif result.get("status") == "error":
    st.error(result.get("message", "The query pipeline failed."))

if result.get("status") == "completed" and result.get("predicted_sql"):
    try:
        columns, rows, truncated = execute_readonly(
            DATA_DIR / "database", result.get("db_id", database), result["predicted_sql"]
        )
        st.session_state["query_rows"] = (columns, rows, truncated)
        st.session_state["query_execution_error"] = ""
    except Exception as exc:
        st.session_state["query_rows"] = None
        st.session_state["query_execution_error"] = str(exc)


# ---------- CLARIFICATION COLUMN ----------
with clarification_col:
    st.markdown("### Clarification")

    if result.get("status") == "clarification_required":
        st.caption("Answer the clarification prompt above to continue.")
        if result.get("reason"):
            st.caption(result["reason"])
    elif result.get("status") == "completed":
        st.success("Question understood. SQL has been generated.")
    else:
        st.markdown(
            "If your question is ambiguous or missing "
            "important details, a follow-up question "
            "will appear here."
        )

    st.markdown("---")
    st.markdown("**Example questions**")
    st.caption("• Show monthly sales by region")
    st.caption("• Find the top five products by revenue")
    st.caption("• Count employees in each department")


# ---------- SQL + RESULTS COLUMNS ----------
st.divider()

sql_col, results_col = st.columns(
    [1, 1],
    gap="large"
)

with sql_col:
    st.markdown("### Generated SQL")

    if result.get("predicted_sql"):
        st.caption("Generated from your question")
        st.code(result["predicted_sql"], language="sql")
    else:
        st.caption(
            "Your generated SQL query will appear here."
        )

with results_col:
    st.markdown("### Query results")

    if result.get("status") == "completed":
        execution_error = st.session_state.get("query_execution_error", "")
        query_rows = st.session_state.get("query_rows")
        if execution_error:
            st.error(f"SQL was generated, but execution failed: {execution_error}")
        elif query_rows:
            columns, rows, truncated = query_rows
            st.dataframe(
                [dict(zip(columns, row)) for row in rows],
                use_container_width=True,
            )
            st.caption(f"{len(rows)} rows returned" + (" (showing first 500)." if truncated else "."))
        else:
            st.caption("No results are available yet.")
    else:
        st.caption(
            "Results will appear here after "
            "the query executes successfully."
        )


# ---------- FOOTER ----------
st.divider()

st.markdown(
    '<div class="footer">'
    'QueryClarify AI · Ask clearly. Query intelligently.'
    '</div>',
    unsafe_allow_html=True
)
