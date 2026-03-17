import streamlit as st
import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe
from google.oauth2.service_account import Credentials
import time

# ------------------------------------
# GOOGLE SHEETS CONNECTION (CACHED)
# ------------------------------------
@st.cache_data(ttl=60)  # Refresh every 60 seconds
def load_sheet(sheet_id, worksheet_name):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_file(
        "service_account.json", scopes=scopes
    )
    client = gspread.authorize(credentials)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.worksheet(worksheet_name)

    df = get_as_dataframe(worksheet, evaluate_formulas=True)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df


# ------------------------------------
# DATA CLEANING
# ------------------------------------
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = (
        df.columns
        .str.strip().str.lower().str.replace(" ", "_").str.replace("-", "_")
    )

    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()

    for col in df.columns:
        if "date" in col or "time" in col:
            try:
                df[col] = pd.to_datetime(df[col], errors="ignore")
            except:
                pass

    df = df.replace("", pd.NA)
    return df


# ------------------------------------
# STREAMLIT UI
# ------------------------------------
st.set_page_config(page_title="Live M&E Dashboard", layout="wide")

st.title("📊 Live M&E Dashboard")
st.caption("Phase 5 — Auto-Refresh & Caching")

# Refresh control
col1, col2 = st.columns([1, 4])

with col1:
    refresh_now = st.button("🔄 Refresh Data Now")

with col2:
    st.info("Data auto-refreshes every 60 seconds.")

# Sheet settings
SHEET_ID = "1lkztBZ4eG1BQx-52XgnA6w8YIiw-Sm85pTlQQziurfw"
WORKSHEET_NAME = "QC_Log"

# Force refresh cache when button clicked
if refresh_now:
    # Clear cached data for this function
    load_sheet.clear()
    st.success("Cache cleared! Fetching fresh data...")
    time.sleep(0.3)
    # Rerun the app (new API)
    try:
        st.rerun()
    except AttributeError:
        # Fallback for very old Streamlit versions
        st.experimental_rerun()

try:
    # Load & clean data
    raw_df = load_sheet(SHEET_ID, WORKSHEET_NAME)
    clean_df = clean_data(raw_df)

    # ---------------- Sidebar Filters ----------------
    st.sidebar.header("🔎 Filters")

    filter_columns = [col for col in clean_df.columns if clean_df[col].dtype == "object"]

    active_filters = {}
    for col in filter_columns:
        unique_vals = clean_df[col].dropna().unique().tolist()
        selected_vals = st.sidebar.multiselect(f"Filter by {col}", unique_vals)
        active_filters[col] = selected_vals

    # Apply filters
    filtered_df = clean_df.copy()
    for col, values in active_filters.items():
        if values:
            filtered_df = filtered_df[filtered_df[col].isin(values)]

    # ---------------- Tabs Layout ----------------
    tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Trends", "Geographic", "Raw Data"])

    # -------- Tab 1
    with tab1:
        st.subheader("Overview Dashboard")
        st.write("Define your KPIs later.")

        st.metric("Total Records", len(filtered_df))

    # -------- Tab 2
    with tab2:
        st.subheader("Trends Over Time")

        date_col = None
        for col in filtered_df.columns:
            if "date" in col:
                date_col = col
                break

        if date_col is not None and pd.api.types.is_datetime64_any_dtype(filtered_df[date_col]):
            tmp = filtered_df.copy()
            tmp["_month"] = tmp[date_col].dt.to_period("M").astype(str)
            monthly = tmp["_month"].value_counts().sort_index()
            st.line_chart(monthly)
        else:
            st.info("No detected (parsed) date column. We'll wire this up when you share your real column names.")

    # -------- Tab 3
    with tab3:
        st.subheader("Geographic Breakdown")

        if "province" in filtered_df.columns:
            province_counts = filtered_df["province"].value_counts()
            st.bar_chart(province_counts)
        else:
            st.info("No province column detected.")

    # -------- Tab 4
    with tab4:
        st.subheader("Raw Data")
        st.dataframe(filtered_df, use_container_width=True)

except Exception as e:
    st.error("Failed to load data.")
    st.code(str(e))