import streamlit as st
import pandas as pd
import gspread
import json
import plotly.express as px
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(
    page_title="M&E Dashboard",
    layout="wide"
)

st.title("📊 Live M&E Dashboard — Phase 8 (Full Production)")
st.caption("Built with ❤️ by Amor & Ahmad")

# ---------------------------------------------------
# AFGHANISTAN PROVINCE GEOJSON (BUILT-IN)
# ---------------------------------------------------
afg_geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "id": "Badakhshan",
            "properties": {"name": "Badakhshan"},
            "geometry": {"type": "Polygon", "coordinates": [[[71.0, 37.0], [72.0, 37.0], [72.0, 36.0], [71.0, 36.0], [71.0, 37.0]]]}
        }
        # ❗ NOTE:
        # This is only a placeholder geometry.
        # In Streamlit Cloud this will still render — but for real shapes,
        # I will send you a full real GeoJSON file in the next message.
    ]
}

# ---------------------------------------------------
# LOAD GOOGLE SHEET (CACHED)
# ---------------------------------------------------
@st.cache_data(ttl=60)
def load_sheet(sheet_id, worksheet_name):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    gcp_info = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    credentials = Credentials.from_service_account_info(gcp_info, scopes=scopes)

    client = gspread.authorize(credentials)
    sheet = client.open_by_key(sheet_id)
    worksheet = sheet.worksheet(worksheet_name)

    df = get_as_dataframe(worksheet, evaluate_formulas=True)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df


# ---------------------------------------------------
# CLEAN DATA
# ---------------------------------------------------
def clean_data(df):
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    for col in df.select_dtypes(include="object"):
        df[col] = df[col].astype(str).str.strip()

    # Convert date columns
    for col in df.columns:
        if "date" in col:
            df[col] = pd.to_datetime(df[col], errors="ignore")

    return df


# ---------------------------------------------------
# LOAD DATA
# ---------------------------------------------------
SHEET_ID = "1lkztBZ4eG1BQx-52XgnA6w8YIiw-Sm85pTlQQziurfw"
WORKSHEET_NAME = "QC_Log"

with st.sidebar:
    st.header("🔄 Data Controls")
    refresh_button = st.button("Refresh Now")

if refresh_button:
    load_sheet.clear()
    st.success("Cache cleared! Fetching fresh data...")
    st.rerun()

try:
    raw_df = load_sheet(SHEET_ID, WORKSHEET_NAME)
    df = clean_data(raw_df)
except Exception as e:
    st.error("⚠ Failed to load data")
    st.code(str(e))
    st.stop()

# ---------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------
st.sidebar.header("🔎 Filters")

filter_cols = [col for col in df.columns if df[col].dtype == "object"]

active_filters = {}
for col in filter_cols:
    values = df[col].dropna().unique().tolist()
    selected = st.sidebar.multiselect(f"{col}", values)
    active_filters[col] = selected

filtered = df.copy()
for col, vals in active_filters.items():
    if vals:
        filtered = filtered[filtered[col].isin(vals)]

# ---------------------------------------------------
# KPI FUNCTIONS
# ---------------------------------------------------
def kpi_card(label, value, color):
    st.markdown(
        f"""
        <div style="
            background-color:{color};
            padding:20px;
            border-radius:10px;
            text-align:center;
            color:white;
            font-size:22px;
            font-weight:bold;">
            {label}<br>
            <span style="font-size:35px;">{value}</span>
        </div>
        """,
        unsafe_allow_html=True
    )


# ---------------------------------------------------
# TABS
# ---------------------------------------------------
tab_overview, tab_trends, tab_geo, tab_qc, tab_raw = st.tabs(
    ["🏠 Overview", "📈 Trends", "🗺 Geographic", "🛠 QC Logs", "📄 Raw Data"]
)

# ---------------------------------------------------
# TAB 1 — OVERVIEW
# ---------------------------------------------------
with tab_overview:
    st.subheader("📊 Key Performance Indicators")

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        kpi_card("Total Submissions", len(filtered["key"].unique()), "#6A5ACD")

    with col2:
        assigned = filtered["qc_by"].replace("", pd.NA).dropna()
        kpi_card("Assigned to QC", len(assigned), "#4682B4")

    with col3:
        qaed = filtered["status"].replace("", pd.NA).dropna()
        kpi_card("Total QA'ed", len(qaed), "#2E8B57")

    with col4:
        approved = sum(filtered["status"] == "Approved")
        kpi_card("Approved", approved, "#228B22")

    with col5:
        rejected = sum(filtered["status"] == "Rejected")
        kpi_card("Rejected", rejected, "#B22222")

    with col6:
        pending = sum(filtered["status"] == "Pending")
        kpi_card("Pending", pending, "#FF8C00")

    st.markdown("---")

    # Summary charts
    st.subheader("📌 Summary Charts")

    colA, colB = st.columns(2)

    with colA:
        try:
            st.write("### Status Distribution")
            st.plotly_chart(
                px.pie(
                    filtered,
                    names="status",
                    title="Approved vs Rejected vs Pending"
                ),
                use_container_width=True
            )
        except:
            st.info("No status data")

    with colB:
        try:
            st.write("### Submissions by Province")
            st.plotly_chart(
                px.bar(
                    filtered["province"].value_counts().reset_index(),
                    x="index",
                    y="province",
                    labels={"index": "Province", "province": "Count"},
                ),
                use_container_width=True
            )
        except:
            st.info("Province column missing")

# ---------------------------------------------------
# TAB 2 — TRENDS
# ---------------------------------------------------
with tab_trends:
    st.subheader("📈 Trend Analysis")

    trend_mode = st.radio(
        "Select Trend Type",
        ["Daily", "Weekly", "Monthly"],
        horizontal=True
    )

    if "survey_date" in filtered.columns:
        temp = filtered.copy()
        temp = temp[temp["survey_date"].notna()]

        if trend_mode == "Daily":
            temp["_time"] = temp["survey_date"].dt.date
        elif trend_mode == "Weekly":
            temp["_time"] = temp["survey_date"].dt.to_period("W").astype(str)
        else:
            temp["_time"] = temp["survey_date"].dt.to_period("M").astype(str)

        trend = temp["_time"].value_counts().sort_index()

        st.plotly_chart(px.line(trend, title=f"{trend_mode} Trend"), use_container_width=True)

# ---------------------------------------------------
# TAB 3 — GEOGRAPHIC
# ---------------------------------------------------
with tab_geo:
    st.subheader("🗺 Province Map")

    if "province" in filtered.columns:
        province_counts = filtered["province"].value_counts().reset_index()
        province_counts.columns = ["province", "count"]

        fig_map = px.choropleth(
            province_counts,
            geojson=afg_geojson,
            featureidkey="properties.name",
            locations="province",
            color="count",
            color_continuous_scale="Blues",
            title="Submissions by Province"
        )
        fig_map.update_geos(fitbounds="locations", visible=False)

        st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("Province column missing.")

# ---------------------------------------------------
# TAB 4 — QC LOGS
# ---------------------------------------------------
with tab_qc:
    st.subheader("🛠 QC Performance Dashboard")

    if "qc_by" in filtered.columns:
        qc_counts = filtered["qc_by"].value_counts().reset_index()
        qc_counts.columns = ["qc_by", "count"]

        st.write("### QC Reviewer Activity")
        st.plotly_chart(
            px.bar(
                qc_counts,
                x="qc_by",
                y="count",
                labels={"qc_by": "QC Reviewer", "count": "Logs Reviewed"},
                title="QC Team Productivity"
            ),
            use_container_width=True
        )
    else:
        st.info("QC columns missing.")

# ---------------------------------------------------
# TAB 5 — RAW DATA
# ---------------------------------------------------
with tab_raw:
    st.subheader("📄 Full Dataset")
    st.dataframe(filtered, use_container_width=True)

    st.download_button(
        "Download CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        "filtered_data.csv",
        "text/csv"
    )
