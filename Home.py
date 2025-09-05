import streamlit as st
import pandas as pd
import plotly.express as px
from rapidfuzz import fuzz
from datetime import datetime

# -----------------------------
# Page Config
# -----------------------------
st.set_page_config(page_title="💊 Medicine Mismatch Detector", layout="wide")

# -----------------------------
# Load Data
# -----------------------------
@st.cache_data
def load_medicine_data():
    # Example dataset (replace with your own DB/file if needed)
    data = {
        "Medicine Name": [
            "Paracetamol", "Amoxicillin", "Ciprofloxacin", "Metformin", "Ibuprofen",
            "Azithromycin", "Cetirizine", "Omeprazole", "Atorvastatin", "Amlodipine"
        ]
    }
    return pd.DataFrame(data)

medicine_df = load_medicine_data()

# -----------------------------
# Session State for history
# -----------------------------
if "history" not in st.session_state:
    st.session_state.history = []

# -----------------------------
# Sidebar Navigation
# -----------------------------
st.sidebar.title("⚙️ Navigation")
page = st.sidebar.radio("Go to", ["Detector", "Search Medicines", "History", "Analytics"])

# -----------------------------
# Detector Page
# -----------------------------
if page == "Detector":
    st.title("💊 Medicine Mismatch Detector")
    st.write("Upload a prescription file or manually enter medicine names to detect mismatches.")

    uploaded_file = st.file_uploader("📂 Upload Prescription (CSV/TXT)", type=["csv", "txt"])

    if uploaded_file is not None:
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            st.dataframe(df)
            medicines_list = df.iloc[:, 0].tolist()
        else:
            text_data = uploaded_file.read().decode("utf-8").splitlines()
            medicines_list = [line.strip() for line in text_data if line.strip()]
    else:
        medicines_list = st.text_area("Or enter medicines (comma separated):").split(",")

    # ✅ Fix: Convert all values to string before processing
    medicines_list = [str(m).strip().capitalize() for m in medicines_list if str(m).strip()]

    if st.button("🔍 Detect Mismatches"):
        results = []
        for med in medicines_list:
            best_match = None
            best_score = 0
            for ref in medicine_df["Medicine Name"]:
                score = fuzz.ratio(med.lower(), ref.lower())
                if score > best_score:
                    best_score = score
                    best_match = ref

            results.append({
                "Entered": med,
                "Closest Match": best_match,
                "Match Score": best_score,
                "Mismatch": "❌ Yes" if best_score < 90 else "✅ No"
            })

        result_df = pd.DataFrame(results)
        st.dataframe(result_df)

        # 📊 Bar chart of match scores
        st.subheader("📊 Match Score Comparison")
        fig = px.bar(result_df, x="Entered", y="Match Score", color="Mismatch",
                     text="Closest Match", title="Medicine Match Scores")
        st.plotly_chart(fig, use_container_width=True)

        # Save in history
        st.session_state.history.append({
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": result_df
        })

# -----------------------------
# Search Medicines
# -----------------------------
elif page == "Search Medicines":
    st.title("🔎 Search Medicine Database")
    query = st.text_input("Enter medicine name:")
    if query:
        matches = []
        for ref in medicine_df["Medicine Name"]:
            score = fuzz.ratio(query.lower(), ref.lower())
            if score > 60:  # show only close matches
                matches.append((ref, score))

        if matches:
            st.success("Possible matches found:")
            for m, s in sorted(matches, key=lambda x: -x[1]):
                st.write(f"✅ {m} ({s:.0f}%)")
        else:
            st.error("No close matches found!")

# -----------------------------
# History Page
# -----------------------------
elif page == "History":
    st.title("📜 Detection History")
    if st.session_state.history:
        for record in st.session_state.history[::-1]:
            st.subheader(f"🕒 {record['time']}")
            st.dataframe(record["results"])
    else:
        st.info("No history available yet.")

# -----------------------------
# Analytics Page
# -----------------------------
elif page == "Analytics":
    st.title("📊 Analytics")
    if st.session_state.history:
        mismatch_counts = {"Mismatch": 0, "Correct": 0}
        for record in st.session_state.history:
            mismatch_counts["Mismatch"] += (record["results"]["Mismatch"] == "❌ Yes").sum()
            mismatch_counts["Correct"] += (record["results"]["Mismatch"] == "✅ No").sum()

        mismatch_df = pd.DataFrame(list(mismatch_counts.items()), columns=["Status", "Count"])

        # Pie chart
        fig1 = px.pie(mismatch_df, values="Count", names="Status", title="Mismatch vs Correct Detections")
        st.plotly_chart(fig1, use_container_width=True)

        # Bar chart
        st.subheader("📊 Bar Chart: Detection Status")
        fig2 = px.bar(mismatch_df, x="Status", y="Count", color="Status",
                      title="Mismatch vs Correct (Counts)")
        st.plotly_chart(fig2, use_container_width=True)

    else:
        st.info("Run some detections to see analytics.")
