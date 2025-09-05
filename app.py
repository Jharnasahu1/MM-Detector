import streamlit as st
import pandas as pd
import plotly.express as px
from rapidfuzz import fuzz, process
from datetime import datetime
import os

# ---------------------------------
# Page Config
# ---------------------------------
st.set_page_config(page_title="💊 Medicine Mismatch Detector", layout="wide")

# ---------------------------------
# Helpers
# ---------------------------------
def normalize_series(s: pd.Series) -> pd.Series:
    """Lowercase+strip for matching, keep original for display elsewhere."""
    return s.astype(str).str.strip().str.lower()

def guess_name_column(df: pd.DataFrame) -> int:
    """Guess which column holds medicine names, fallback to first column."""
    candidates = {"medicine", "medicine name", "drug", "brand", "name", "product"}
    cols = [c for c in df.columns]
    for i, c in enumerate(cols):
        if c.strip().lower() in candidates:
            return i
    return 0 if cols else -1

# ---------------------------------
# Initialize Session State
# ---------------------------------
if "results" not in st.session_state:
    st.session_state["results"] = pd.DataFrame()
if "reference_df" not in st.session_state:
    st.session_state["reference_df"] = None  # allows per-session override with uploaded file

# ---------------------------------
# Load Default Reference Data
# ---------------------------------
@st.cache_data
def load_default_reference():
    # Default reference DB; replace with your own file if you like.
    # If you already have "all_medicines.csv", uncomment the next line and delete inline data.
    # return pd.read_csv("all_medicines.csv")

    data = [
        ["Paracetamol", 15, "Cipla", "Allopathy", "Strip of 10 tablets"],
        ["Ibuprofen", 25, "Sun Pharma", "Allopathy", "Strip of 10 tablets"],
        ["Metformin", 35, "Torrent", "Allopathy", "Strip of 15 tablets"],
        ["Amoxicillin", 50, "Dr Reddy", "Allopathy", "Strip of 10 tablets"],
        ["Ciprofloxacin", 40, "Alkem", "Allopathy", "Strip of 10 tablets"],
        ["Cetirizine", 20, "Lupin", "Allopathy", "Strip of 15 tablets"],
        ["Omeprazole", 30, "Zydus", "Allopathy", "Strip of 10 capsules"],
        ["Atorvastatin", 60, "Sun Pharma", "Allopathy", "Strip of 10 tablets"],
        ["Azithromycin", 55, "Abbott", "Allopathy", "Strip of 6 tablets"],
        ["Amlodipine", 28, "Glenmark", "Allopathy", "Strip of 10 tablets"],
        ["Ashwagandha", 120, "Himalaya", "Ayurvedic", "Bottle of 60 capsules"],
        ["Triphala", 90, "Baidyanath", "Ayurvedic", "Bottle of 100 g powder"],
        ["Chyawanprash", 250, "Dabur", "Ayurvedic", "Bottle of 500 g"],
    ]
    return pd.DataFrame(data, columns=["Medicine Name", "Price", "Company", "Category", "Packaging"])

# Use either the uploaded reference (if any) or the default
def get_reference_df():
    return st.session_state["reference_df"] if st.session_state["reference_df"] is not None else load_default_reference()

# ---------------------------------
# History File Setup
# ---------------------------------
HISTORY_FILE = "history.csv"
if not os.path.exists(HISTORY_FILE):
    pd.DataFrame(columns=["Time", "Entered", "Closest Match", "Match Score", "Status"]).to_csv(HISTORY_FILE, index=False)

def save_history(results_df: pd.DataFrame):
    df_copy = results_df.copy()
    df_copy["Time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df_copy[["Time", "Entered", "Closest Match", "Match Score", "Status"]].to_csv(
        HISTORY_FILE, mode="a", header=False, index=False
    )

def load_history():
    return pd.read_csv(HISTORY_FILE)

# ---------------------------------
# Sidebar Navigation
# ---------------------------------
st.sidebar.title("📌 Navigation")
app_mode = st.sidebar.radio("Go to", ["Detector", "Search Medicines", "History", "Analytics"])

# ---------------------------------
# Detector
# ---------------------------------
if app_mode == "Detector":
    st.title("💊 Medicine Mismatch Detector")
    st.write("Upload a file **or** type medicine names to check against the reference database.")

    with st.expander("📂 Upload a CSV/Excel file", expanded=True):
        uploaded_file = st.file_uploader("Choose file", type=["csv", "xlsx"])
        df_uploaded = None
        selected_col = None
        use_as_reference = False

        if uploaded_file is not None:
            if uploaded_file.name.lower().endswith(".csv"):
                df_uploaded = pd.read_csv(uploaded_file)
            else:
                df_uploaded = pd.read_excel(uploaded_file)  # requires openpyxl
            if not df_uploaded.empty:
                st.caption("Preview of uploaded file")
                st.dataframe(df_uploaded.head(10), use_container_width=True)

                # Let user choose which column contains medicine names
                default_idx = guess_name_column(df_uploaded)
                selected_col = st.selectbox(
                    "Column containing medicine names",
                    options=list(df_uploaded.columns),
                    index=max(default_idx, 0),
                )

                # Optional: Use this file as the reference database
                use_as_reference = st.checkbox(
                    "Use this file as the reference database (instead of built-in)",
                    value=False,
                    help="If checked, the selected column becomes the reference 'Medicine Name' list for this session."
                )

    user_input = st.text_area("Or enter medicine names (comma separated)", "")

    run = st.button("🔎 Detect Mismatches", type="primary")

    if run:
        # Build entered list
        entered_list = []

        # From uploaded file (as entries)
        if df_uploaded is not None and selected_col is not None and not use_as_reference:
            entered_list += (
                df_uploaded[selected_col]
                .dropna()
                .astype(str)
                .str.strip()
                .tolist()
            )

        # From manual input
        if user_input.strip():
            entered_list += [x.strip() for x in user_input.split(",") if x.strip()]

        # Clean & dedupe
        entered_list = [e for e in entered_list if e]
        # Deduplicate preserving order
        seen = set()
        entered_list = [x for x in entered_list if not (x.lower() in seen or seen.add(x.lower()))]

        if use_as_reference and df_uploaded is not None and selected_col is not None:
            # Set uploaded file as reference for this session
            ref_df = df_uploaded.rename(columns={selected_col: "Medicine Name"}).copy()
            if "Medicine Name" not in ref_df.columns:
                ref_df.insert(0, "Medicine Name", df_uploaded[selected_col].astype(str))
            st.session_state["reference_df"] = ref_df

        # If nothing to check, notify
        if not entered_list:
            st.warning("Please upload a file or type at least one medicine name.")
        else:
            # Prepare reference list
            ref_df = get_reference_df()
            if "Medicine Name" not in ref_df.columns:
                st.error("Reference data must contain a 'Medicine Name' column.")
            else:
                ref_names_display = ref_df["Medicine Name"].dropna().astype(str).str.strip()
                ref_names_norm = normalize_series(ref_names_display).tolist()

                # Match each entry
                results = []
                for med in entered_list:
                    med_norm = med.strip().lower()
                    match = process.extractOne(
                        med_norm,
                        ref_names_norm,
                        scorer=fuzz.token_sort_ratio
                    )
                    if match:
                        matched_norm, score, idx = match
                        closest_display = ref_names_display.iloc[idx]
                        # Status thresholds
                        if score >= 95:
                            status = "✅ Correct"
                        elif score >= 70:
                            status = "⚠️ Possible Mismatch"
                        else:
                            status = "❌ Mismatch"
                        results.append({
                            "Entered": med,
                            "Closest Match": closest_display,
                            "Match Score": float(score),
                            "Status": status
                        })
                    else:
                        results.append({
                            "Entered": med,
                            "Closest Match": "—",
                            "Match Score": 0.0,
                            "Status": "❌ Mismatch"
                        })

                results_df = pd.DataFrame(results)

                # Persist & log
                st.session_state["results"] = results_df
                save_history(results_df)

    # Show last results (persisted across panels)
    if not st.session_state["results"].empty:
        st.subheader("🔍 Results")
        st.dataframe(st.session_state["results"], use_container_width=True)

        st.subheader("📊 Match Score Comparison")
        fig = px.bar(
            st.session_state["results"],
            x="Entered",
            y="Match Score",
            color="Status",
            text="Closest Match",
            title="Similarity scores per entry",
            height=420
        )
        st.plotly_chart(fig, use_container_width=True)

# ---------------------------------
# Search Medicines
# ---------------------------------
elif app_mode == "Search Medicines":
    st.title("🔎 Search Medicines in Reference DB")
    ref_df = get_reference_df()
    query = st.text_input("Search by name")
    if query:
        mask = ref_df["Medicine Name"].astype(str).str.contains(query, case=False, na=False)
        st.dataframe(ref_df[mask], use_container_width=True)
    else:
        st.dataframe(ref_df.head(25), use_container_width=True)
    st.caption("Tip: You can switch the reference DB on the Detector tab by uploading a file and ticking 'Use this file as the reference database'.")

# ---------------------------------
# History
# ---------------------------------
elif app_mode == "History":
    st.title("📜 Detection History")
    hist = load_history()
    if hist.empty:
        st.info("No history yet.")
    else:
        st.dataframe(hist, use_container_width=True)
        # Quick filter
        only_mismatch = st.checkbox("Show mismatches only", value=False)
        if only_mismatch:
            st.dataframe(hist[hist["Status"].str.contains("Mismatch")], use_container_width=True)

# ---------------------------------
# Analytics
# ---------------------------------
elif app_mode == "Analytics":
    st.title("📊 Analytics")
    ref_df = get_reference_df()

    st.subheader("Reference Database Overview")
    if not ref_df.empty:
        show_cols = [c for c in ["Medicine Name", "Company", "Category", "Price"] if c in ref_df.columns]
        st.dataframe(ref_df[show_cols].head(30), use_container_width=True)

        if "Price" in ref_df.columns:
            fig_prices = px.bar(ref_df, x="Medicine Name", y="Price", color=ref_df.get("Company"),
                                title="Prices by medicine", height=420)
            st.plotly_chart(fig_prices, use_container_width=True)

    st.subheader("History Summary")
    hist = load_history()
    if hist.empty:
        st.info("Run a detection to populate analytics.")
    else:
        if "Status" not in hist.columns:
            st.error("⚠️ Your `history.csv` file is outdated (missing 'Status' column). Please delete it and rerun detection.")
        else:
            counts = hist["Status"].value_counts().reset_index()
            counts.columns = ["Status", "Count"]
            fig_hist = px.bar(counts, x="Status", y="Count", color="Status", title="Detections by status")
            st.plotly_chart(fig_hist, use_container_width=True)


