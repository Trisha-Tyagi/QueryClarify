
import streamlit as st
from pathlib import Path

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

    database = st.selectbox(
        "Choose database",
        ["Demo database"]
    )

    st.caption(
        "Configure your actual database "
        "during backend integration."
    )

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


# ---------- HANDLE SUBMISSION ----------
if submitted:
    if question_input.strip():
        st.session_state["question"] = question_input.strip()
        st.session_state["submitted"] = True
    else:
        st.session_state["submitted"] = False
        st.warning("Please enter a question first.")


# ---------- CLARIFICATION COLUMN ----------
with clarification_col:
    st.markdown("### Clarification")

    if st.session_state["submitted"]:
        st.info(
            "Your question has been received. "
            "The Phase 7 clarification engine will be "
            "connected here."
        )
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

    if st.session_state["submitted"]:
        st.caption("Based on your question")

        st.code(
            "-- SQL generation will be connected here",
            language="sql"
        )
    else:
        st.caption(
            "Your generated SQL query will appear here."
        )

with results_col:
    st.markdown("### Query results")

    if st.session_state["submitted"]:
        st.caption(
            "Database execution will appear here "
            "once the backend is connected."
        )
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
