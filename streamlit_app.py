import io
import hashlib
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Comparison between Sell IN RF Taiwan", layout="wide")

MONTH_ORDER = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"]
FY_ORDER = ["FY24", "FY25", "FY26", "FY27"]
PUBLISH_ORDER = [
    "RF1", "RF2", "RF3", "RF4", "RF5", "RF6", "RF7", "RF8", "RF9", "RF10",
    "RF11", "RF12",
    "RF1_FY26", "RF2_FY26", "RF3_FY26", "RF4_FY26", "RF5_FY26",
    "RF6_FY26", "RF7_FY26", "RF8_FY26", "RF9_FY26"
]

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 1.2rem;}
    .metric-card {
        border: 1px solid #E5E7EB; border-radius: 12px; padding: 0.8rem 1rem;
        background: linear-gradient(180deg, #FFFFFF 0%, #FAFAFA 100%);
    }
    .metric-label {font-size: 0.82rem; color: #6B7280; margin-bottom: 0.15rem;}
    .metric-value {font-size: 1.5rem; font-weight: 700; color: #111827;}
    .subtle {color: #6B7280; font-size: 0.85rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def _hash_bytes(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


@st.cache_data(show_spinner=False)
def read_csv_cached(file_bytes: bytes, file_name: str) -> pd.DataFrame:
    try:
        return pd.read_csv(io.BytesIO(file_bytes))
    except UnicodeDecodeError:
        return pd.read_csv(io.BytesIO(file_bytes), encoding="latin1")


@st.cache_data(show_spinner=False)
def read_csv_from_url_cached(file_url: str) -> tuple[pd.DataFrame, bytes]:
    with urlopen(file_url) as response:
        file_bytes = response.read()
    if len(file_bytes) <= 2:
        raise ValueError(f"Remote file looks empty: {file_url}")
    return read_csv_cached(file_bytes, file_url.split("/")[-1]), file_bytes


def build_github_raw_url(owner: str, repo: str, branch: str, folder: str, file_name: str) -> str:
    clean_folder = folder.strip("/")
    folder_part = f"/{quote(clean_folder)}" if clean_folder else ""
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}{folder_part}/{quote(file_name)}"


def load_csv(uploaded_file, fallback_path: str, session_key: str, file_url: str | None = None, source_label: str | None = None):
    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        df = read_csv_cached(file_bytes, uploaded_file.name)
        st.session_state[session_key] = df
        st.session_state[f"{session_key}_name"] = uploaded_file.name
        st.session_state[f"{session_key}_hash"] = _hash_bytes(file_bytes)
        st.session_state[f"{session_key}_source"] = "Uploaded file"
        return df

    cached_hash = st.session_state.get(f"{session_key}_hash")
    if session_key in st.session_state and st.session_state.get(f"{session_key}_source") == source_label:
        return st.session_state[session_key]

    if file_url:
        try:
            df, file_bytes = read_csv_from_url_cached(file_url)
            new_hash = _hash_bytes(file_bytes)
            if cached_hash != new_hash:
                st.session_state[session_key] = df
                st.session_state[f"{session_key}_name"] = file_url.split("/")[-1]
                st.session_state[f"{session_key}_hash"] = new_hash
                st.session_state[f"{session_key}_source"] = source_label or "GitHub raw URL"
            return st.session_state[session_key]
        except Exception as e:
            st.warning(f"Could not load {file_url}: {e}")

    p = Path(fallback_path)
    if p.exists():
        file_bytes = p.read_bytes()
        if len(file_bytes) <= 2:
            st.warning(f"Local fallback file looks empty: {p.name}")
            return None
        df = read_csv_cached(file_bytes, p.name)
        st.session_state[session_key] = df
        st.session_state[f"{session_key}_name"] = p.name
        st.session_state[f"{session_key}_hash"] = _hash_bytes(file_bytes)
        st.session_state[f"{session_key}_source"] = source_label or "Local file"
        return df
    return None


def ensure_unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    seen = {}
    new_cols = []
    for c in [str(x) for x in out.columns]:
        if c not in seen:
            seen[c] = 0
            new_cols.append(c)
        else:
            seen[c] += 1
            new_cols.append(f"{c}_{seen[c]}")
    out.columns = new_cols
    return out


def safe_dataframe(df: pd.DataFrame, **kwargs):
    st.dataframe(ensure_unique_columns(df), **kwargs)


@st.cache_data(show_spinner=False)
def dataframe_to_download_bytes(df: pd.DataFrame, preferred_format: str = "xlsx"):
    df = ensure_unique_columns(df)
    if preferred_format == "xlsx":
        for engine in ["openpyxl", "xlsxwriter"]:
            try:
                bio = io.BytesIO()
                with pd.ExcelWriter(bio, engine=engine) as writer:
                    df.to_excel(writer, index=False, sheet_name="data")
                return bio.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
            except Exception:
                pass
    return df.to_csv(index=False).encode("utf-8-sig"), "text/csv", "csv"


def download_button(df: pd.DataFrame, label: str, file_stub: str, key: str):
    data, mime, ext = dataframe_to_download_bytes(df)
    st.download_button(label, data=data, file_name=f"{file_stub}.{ext}", mime=mime, key=key)


def fmt_int(x):
    try:
        return f"{int(round(float(x))):,}"
    except Exception:
        return ""


def fmt_pct(x):
    try:
        return f"{float(x):.1%}"
    except Exception:
        return ""


def metric_card(title: str, value: str):
    st.markdown(
        f"<div class='metric-card'><div class='metric-label'>{title}</div><div class='metric-value'>{value}</div></div>",
        unsafe_allow_html=True,
    )


def prepare_main_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ["brand", "brand_quality", "brand_quality_size", "pig_description", "pig_code", "higher_channel_lst", "customer_group_name", "customer_groups_channel_lst", "CentralStatus"]:
        if c in out.columns:
            out[c] = out[c].astype(str)

    if "brand_quality" in out.columns:
        out["brand_quality"] = out["brand_quality"].astype(str)
    if "brand_quality_size" in out.columns:
        out["brand_quality_size"] = out["brand_quality_size"].astype(str)
    if "pig_description" in out.columns:
        out["pig_description"] = out["pig_description"].astype(str)

    if "calendar_month_abb" in out.columns:
        out["calendar_month_abb"] = pd.Categorical(out["calendar_month_abb"], categories=MONTH_ORDER, ordered=True)
    if "period" in out.columns:
        out["period"] = pd.to_datetime(out["period"], errors="coerce")
    return out


def prepare_allocation_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    keep = [c for c in ["pig_code", "qty_alloc"] if c in out.columns]
    if keep:
        out = out[keep]
    if "pig_code" in out.columns:
        out["pig_code"] = out["pig_code"].astype(str)
    if "qty_alloc" in out.columns:
        out["qty_alloc"] = pd.to_numeric(out["qty_alloc"], errors="coerce").fillna(0)
    return out


def prepare_pi_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "period" in out.columns:
        out["period"] = pd.to_datetime(out["period"], errors="coerce")
        target = pd.Timestamp("2025-06-01")
        if (out["period"] == target).any():
            out = out[out["period"] == target]
        elif out["period"].notna().any():
            out = out[out["period"] == out["period"].max()]
    for c in ["Demand", "Supply"]:
        if c in out.columns:
            out = out.drop(columns=c)
    for c in ["pig_code", "pig_description", "brand", "brand_quality", "brand_quality_size"]:
        if c in out.columns:
            out[c] = out[c].astype(str)
    if "calendar_month_abb" in out.columns:
        out["calendar_month_abb"] = pd.Categorical(out["calendar_month_abb"], categories=MONTH_ORDER, ordered=True)
    return out


def get_publish_choices(df: pd.DataFrame):
    ordered = [c for c in PUBLISH_ORDER if c in df.columns]
    extra = [c for c in df.columns if str(c).startswith("RF") and c not in ordered]
    return ordered + sorted(extra)


def build_hierarchical_filters(df: pd.DataFrame):
    filters = {}
    if "brand" in df.columns:
        brands = sorted(df["brand"].dropna().astype(str).unique())
        filters["brand"] = st.sidebar.multiselect("Brand", brands)
    else:
        filters["brand"] = []

    scope = df[df["brand"].astype(str).isin(filters["brand"])] if filters["brand"] and "brand" in df.columns else df
    if "brand_quality" in scope.columns:
        vals = sorted(scope["brand_quality"].dropna().astype(str).unique())
        filters["brand_quality"] = st.sidebar.multiselect("Brand Quality", vals)
    else:
        filters["brand_quality"] = []

    scope2 = scope[scope["brand_quality"].astype(str).isin(filters["brand_quality"])] if filters["brand_quality"] and "brand_quality" in scope.columns else scope
    if "pig_description" in scope2.columns:
        vals = sorted(scope2["pig_description"].dropna().astype(str).unique())
        filters["pig_description"] = st.sidebar.multiselect("PIG Description", vals)
    else:
        filters["pig_description"] = []

    scope3 = scope2[scope2["pig_description"].astype(str).isin(filters["pig_description"])] if filters["pig_description"] and "pig_description" in scope2.columns else scope2
    if "pig_code" in scope3.columns:
        vals = sorted(scope3["pig_code"].dropna().astype(str).unique())
        filters["pig_code"] = st.sidebar.multiselect("PIG Code", vals)
    else:
        filters["pig_code"] = []

    if "higher_channel_lst" in df.columns:
        vals = sorted(df["higher_channel_lst"].dropna().astype(str).unique())
        filters["higher_channel_lst"] = st.sidebar.multiselect("High level Channel List", vals)
    else:
        filters["higher_channel_lst"] = []

    scope4 = df[df["higher_channel_lst"].astype(str).isin(filters["higher_channel_lst"])] if filters["higher_channel_lst"] and "higher_channel_lst" in df.columns else df
    if "customer_group_name" in scope4.columns:
        vals = sorted(scope4["customer_group_name"].dropna().astype(str).unique())
        filters["customer_group_name"] = st.sidebar.multiselect("Customer Group Name", vals)
    else:
        filters["customer_group_name"] = []
    return filters


def apply_filters(df: pd.DataFrame, filters: dict, publish_col: str, period_range=None, date_range_tuple=None):
    out = df.copy()
    for col, vals in filters.items():
        if vals and col in out.columns:
            out = out[out[col].astype(str).isin([str(x) for x in vals])]

    if period_range and "fiscal_month" in out.columns:
        fm = pd.to_numeric(out["fiscal_month"], errors="coerce")
        out = out[(fm >= period_range[0]) & (fm <= period_range[1])]

    if date_range_tuple and "period" in out.columns:
        start_date = pd.to_datetime(date_range_tuple[0])
        end_date = pd.to_datetime(date_range_tuple[1])
        out = out[(out["period"] >= start_date) & (out["period"] <= end_date)]

    if "fiscal_year" in out.columns:
        out = out[out["fiscal_year"].isin(FY_ORDER)]

    out = out.copy()
    out["Publish.Dimension"] = pd.to_numeric(out[publish_col], errors="coerce").fillna(0) if publish_col in out.columns else 0
    return out


def add_dimension(df: pd.DataFrame, dimension_col: str):
    out = df.copy()
    out["Dimension"] = out[dimension_col].astype(str)
    return out


@st.cache_data(show_spinner=False)
def aggregate_overview(df: pd.DataFrame, dimension_col: str, left: str, right: str):
    df = add_dimension(df, dimension_col)
    value = df.groupby(["Dimension", "fiscal_year"], as_index=False)["Publish.Dimension"].sum()
    value = value.pivot(index="Dimension", columns="fiscal_year", values="Publish.Dimension").reset_index()
    for fy in FY_ORDER:
        if fy not in value.columns:
            value[fy] = 0
    value = value[["Dimension"] + FY_ORDER].fillna(0)
    value["delta"] = value[left] - value[right]
    denom = value[right].replace(0, np.nan)
    value["delta.pc"] = (value["delta"] / denom).replace([np.inf, -np.inf], np.nan).fillna(0)
    total = value[left].sum()
    value[f"{left}.pc"] = 0 if total == 0 else value[left] / total

    spark = (
        df.groupby(["Dimension", "calendar_month_abb", "fiscal_year"], as_index=False)["Publish.Dimension"].sum()
        .sort_values(["Dimension", "fiscal_year", "calendar_month_abb"])
    )
    trend = spark.groupby("Dimension")["Publish.Dimension"].apply(list).rename("Quantity")

    month = df.groupby(["Dimension", "calendar_month_abb", "fiscal_year"], as_index=False)["Publish.Dimension"].sum()
    month = month.pivot(index=["Dimension", "calendar_month_abb"], columns="fiscal_year", values="Publish.Dimension").reset_index()
    for fy in FY_ORDER:
        if fy not in month.columns:
            month[fy] = 0
    month["monthly.variation"] = month[left] - month[right]
    mv = month.sort_values(["Dimension", "calendar_month_abb"]).groupby("Dimension")["monthly.variation"].apply(list).rename("FY.Monthly.Variation.Quantity")

    out = value.merge(trend, left_on="Dimension", right_index=True, how="left").merge(mv, left_on="Dimension", right_index=True, how="left")
    return out.sort_values(left, ascending=False)


@st.cache_data(show_spinner=False)
def monthly_fy(df: pd.DataFrame):
    out = df.groupby(["calendar_month_abb", "fiscal_year"], as_index=False)["Publish.Dimension"].sum()
    out["calendar_month_abb"] = pd.Categorical(out["calendar_month_abb"], categories=MONTH_ORDER, ordered=True)
    out = out.sort_values("calendar_month_abb")
    wide = out.pivot(index="calendar_month_abb", columns="fiscal_year", values="Publish.Dimension").reset_index()
    for fy in FY_ORDER:
        if fy not in wide.columns:
            wide[fy] = 0
    return out, wide


def line_chart(df_long, years, title):
    p = df_long[df_long["fiscal_year"].isin(years)].copy()
    p["calendar_month_abb"] = pd.Categorical(p["calendar_month_abb"], categories=MONTH_ORDER, ordered=True)
    p = p.sort_values("calendar_month_abb")
    fig = px.line(p, x="calendar_month_abb", y="Publish.Dimension", color="fiscal_year", markers=True, title=title)
    fig.update_layout(height=330, legend_title=None, margin=dict(l=10, r=10, t=50, b=10))
    fig.update_yaxes(title="in 9LC units")
    fig.update_xaxes(title="")
    return fig


def variation_bar(wide, left, right, title):
    p = wide.copy()
    p["variation"] = p[left] - p[right]
    fig = px.bar(p, x="calendar_month_abb", y="variation", title=title)
    fig.update_traces(marker_color=["#16A34A" if v >= 0 else "#DC2626" for v in p["variation"]])
    fig.update_layout(height=300, showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
    fig.update_yaxes(title="in 9LC units")
    fig.update_xaxes(title="")
    return fig


def quarterly_chart(df_long):
    mapping = {m: "Q1" for m in MONTH_ORDER[:3]} | {m: "Q2" for m in MONTH_ORDER[3:6]} | {m: "Q3" for m in MONTH_ORDER[6:9]} | {m: "Q4" for m in MONTH_ORDER[9:12]}
    q = df_long.copy()
    q["quarter"] = q["calendar_month_abb"].map(mapping)
    q = q.groupby(["quarter", "fiscal_year"], as_index=False)["Publish.Dimension"].sum()
    q["quarter"] = pd.Categorical(q["quarter"], categories=["Q1", "Q2", "Q3", "Q4"], ordered=True)
    q = q.sort_values("quarter")
    fig = px.bar(q, x="quarter", y="Publish.Dimension", color="fiscal_year", barmode="group", title="Quarterly Sales by FY")
    fig.update_layout(height=300, margin=dict(l=10, r=10, t=50, b=10), legend_title=None)
    fig.update_yaxes(title="in 9LC units")
    fig.update_xaxes(title="")
    return fig


def sparkline(series, line_color="#2563EB"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(range(len(series))), y=series, mode="lines", line=dict(width=1.6, color=line_color)))
    fig.update_layout(height=34, width=120, margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def sparkbar(series):
    colors = ["#60A5FA" if v >= 0 else "#F87171" for v in series]
    fig = go.Figure(go.Bar(x=list(range(len(series))), y=series, marker_color=colors))
    fig.update_layout(height=34, width=120, margin=dict(l=0, r=0, t=0, b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def styled_metric_table(df: pd.DataFrame, compare_label: str, left_share: str, key_prefix: str):
    show = df.copy()
    rename_map = {
        "Dimension": "Dimension",
        "FY24": "FY24 (9LC)",
        "FY25": "FY25 (9LC)",
        "FY26": "FY26 (9LC)",
        "FY27": "FY27 (9LC)",
        left_share: f"share of {left_share.replace('.pc','')} Volume (%)",
        "delta": f"{compare_label} (9LC)",
        "delta.pc": f"{compare_label} (%)",
    }
    show = show.rename(columns=rename_map)
    keep = [c for c in [
        "Dimension", "FY24 (9LC)", "FY25 (9LC)", "FY26 (9LC)", "FY27 (9LC)",
        f"share of {left_share.replace('.pc','')} Volume (%)", f"{compare_label} (9LC)", f"{compare_label} (%)"
    ] if c in show.columns]
    display = show[keep].copy()
    safe_dataframe(display.head(1000), use_container_width=True, hide_index=True)

    with st.expander("Mini charts", expanded=False):
        for idx, (_, row) in enumerate(df.head(15).iterrows()):
            c1, c2, c3, c4 = st.columns([3.2, 1.4, 1.4, 1.2])
            c1.write(str(row["Dimension"]))
            with c2:
                st.plotly_chart(sparkline(row.get("Quantity", []) or []), use_container_width=False, config={"displayModeBar": False}, key=f"{key_prefix}_line_{idx}")
            with c3:
                st.plotly_chart(sparkbar(row.get("FY.Monthly.Variation.Quantity", []) or []), use_container_width=False, config={"displayModeBar": False}, key=f"{key_prefix}_bar_{idx}")
            c4.write(fmt_int(row.get("delta", 0)))


@st.cache_data(show_spinner=False)
def compare_publishes(df: pd.DataFrame, filters: dict, old_pub: str, new_pub: str, date_range_tuple, dimension_col: str):
    old_df = apply_filters(df, filters, old_pub, None, date_range_tuple)
    new_df = apply_filters(df, filters, new_pub, None, date_range_tuple)
    old_df = add_dimension(old_df, dimension_col)
    new_df = add_dimension(new_df, dimension_col)

    old_agg = old_df.groupby("Dimension", as_index=False)["Publish.Dimension"].sum().rename(columns={"Publish.Dimension": "old_value"})
    new_agg = new_df.groupby("Dimension", as_index=False)["Publish.Dimension"].sum().rename(columns={"Publish.Dimension": "new_value"})
    diff = old_agg.merge(new_agg, on="Dimension", how="outer").fillna(0)
    diff["delta"] = diff["new_value"] - diff["old_value"]
    diff["delta.pc"] = (diff["delta"] / diff["old_value"].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0)

    old_m = old_df.groupby(["calendar_month_abb"], as_index=False)["Publish.Dimension"].sum().rename(columns={"Publish.Dimension": "old_value"})
    new_m = new_df.groupby(["calendar_month_abb"], as_index=False)["Publish.Dimension"].sum().rename(columns={"Publish.Dimension": "new_value"})
    monthly = old_m.merge(new_m, on="calendar_month_abb", how="outer")
    monthly["old_value"] = pd.to_numeric(monthly["old_value"], errors="coerce").fillna(0)
    monthly["new_value"] = pd.to_numeric(monthly["new_value"], errors="coerce").fillna(0)
    monthly["delta"] = monthly["new_value"] - monthly["old_value"]
    monthly["calendar_month_abb"] = pd.Categorical(monthly["calendar_month_abb"], categories=MONTH_ORDER, ordered=True)
    monthly = monthly.sort_values("calendar_month_abb")
    return diff.sort_values("new_value", ascending=False), monthly


def comparison_charts(monthly: pd.DataFrame, old_pub: str, new_pub: str, key_prefix: str):
    long = monthly.melt(id_vars="calendar_month_abb", value_vars=["old_value", "new_value"], var_name="series", value_name="value")
    long["series"] = long["series"].map({"old_value": old_pub, "new_value": new_pub})
    fig1 = px.line(long, x="calendar_month_abb", y="value", color="series", markers=True, title="Monthly Projections Between Publishes")
    fig1.update_layout(height=300, margin=dict(l=10, r=10, t=45, b=10), legend_title=None)
    fig1.update_yaxes(title="in 9LC units")
    fig1.update_xaxes(title="")
    st.plotly_chart(fig1, use_container_width=True, key=f"{key_prefix}_line")

    fig2 = px.bar(monthly, x="calendar_month_abb", y="delta", title="Upsides / Downsides vs Older Publish")
    fig2.update_traces(marker_color=["#16A34A" if v >= 0 else "#DC2626" for v in monthly["delta"]])
    fig2.update_layout(height=300, margin=dict(l=10, r=10, t=45, b=10), showlegend=False)
    fig2.update_yaxes(title="in 9LC units")
    fig2.update_xaxes(title="")
    st.plotly_chart(fig2, use_container_width=True, key=f"{key_prefix}_bar")


st.title("Comparison between Sell IN RF Taiwan")

with st.sidebar:
    st.caption("Streamlit version aligned more closely to the original Shiny app.R structure.")
    st.subheader("Data sources")
    data_mode = st.radio("Source mode", ["GitHub demo", "Upload CSV files"], index=0)

    github_owner = st.text_input("GitHub owner", value="wayne30691")
    github_repo = st.text_input("GitHub repo", value="WS-Forecast-Tracker")
    github_branch = st.text_input("GitHub branch", value="main")
    github_folder = st.text_input("Data folder", value="Data Source")

    main_url = build_github_raw_url(github_owner, github_repo, github_branch, github_folder, "Set_Up_All_RF_data.csv")
    alloc_url = build_github_raw_url(github_owner, github_repo, github_branch, github_folder, "Allocation_data.csv")
    pi_url = build_github_raw_url(github_owner, github_repo, github_branch, github_folder, "Set_Up_PI_data.csv")

    if data_mode == "GitHub demo":
        st.caption("Default mode: read demo CSV files directly from GitHub raw URLs.")
        st.code(main_url, language=None)
        up_main = up_alloc = up_pi = None
    else:
        up_main = st.file_uploader("Set_Up_All_RF_data.csv", type=["csv"], key="up_main")
        up_alloc = st.file_uploader("Allocation_data.csv", type=["csv"], key="up_alloc")
        up_pi = st.file_uploader("Set_Up_PI_data.csv", type=["csv"], key="up_pi")

main_df = load_csv(
    up_main,
    "/mnt/data/Set_Up_All_RF_data.csv",
    "main_df",
    file_url=main_url if data_mode == "GitHub demo" else None,
    source_label=f"GitHub:{github_owner}/{github_repo}@{github_branch}"
)
allocation_df = load_csv(
    up_alloc,
    "/mnt/data/Allocation_data.csv",
    "allocation_df",
    file_url=alloc_url if data_mode == "GitHub demo" else None,
    source_label=f"GitHub:{github_owner}/{github_repo}@{github_branch}"
)
pi_df = load_csv(
    up_pi,
    "/mnt/data/Set_Up_PI_data.csv",
    "pi_df",
    file_url=pi_url if data_mode == "GitHub demo" else None,
    source_label=f"GitHub:{github_owner}/{github_repo}@{github_branch}"
)

if main_df is None:
    st.info("Provide a non-empty Set_Up_All_RF_data.csv either by GitHub raw URL or file upload to use the app.")
    st.stop()

main_df = prepare_main_df(main_df)
if allocation_df is not None:
    allocation_df = prepare_allocation_df(allocation_df)
if pi_df is not None:
    pi_df = prepare_pi_df(pi_df)

publish_choices = get_publish_choices(main_df)
if not publish_choices:
    st.error("No publish columns detected.")
    st.stop()

with st.sidebar:
    st.subheader("Global controls")
    selected_publish = st.selectbox("Publish Month", publish_choices, index=publish_choices.index("RF9_FY26") if "RF9_FY26" in publish_choices else len(publish_choices)-1)
    old_publish = st.selectbox("Oldest Publish Month", publish_choices, index=publish_choices.index("RF8_FY26") if "RF8_FY26" in publish_choices else 0)
    new_publish = st.selectbox("Newest Publish Month", publish_choices, index=publish_choices.index("RF9_FY26") if "RF9_FY26" in publish_choices else len(publish_choices)-1)

    if "fiscal_month" in main_df.columns:
        fm = pd.to_numeric(main_df["fiscal_month"], errors="coerce").dropna()
        period_range = st.slider("Fiscal Period", int(fm.min()), int(fm.max()), (int(fm.min()), int(fm.max()))) if not fm.empty else None
    else:
        period_range = None

    if "period" in main_df.columns and main_df["period"].notna().any():
        dmin = main_df["period"].min().date()
        dmax = main_df["period"].max().date()
        dr = st.date_input("Date range", (dmin, dmax))
        date_range_tuple = (str(dr[0]), str(dr[1])) if isinstance(dr, tuple) and len(dr) == 2 else None
    else:
        date_range_tuple = None

    threshold = st.date_input("Last 18 months threshold", pd.Timestamp("2024-07-01").date())
    st.subheader("Filters")

filters = build_hierarchical_filters(main_df)
filtered_df = apply_filters(main_df, filters, selected_publish, period_range, date_range_tuple)

with st.expander("Loaded file diagnostics", expanded=False):
    st.write(f"Set_Up_All_RF_data.csv: {main_df.shape[0]:,} rows × {main_df.shape[1]:,} columns")
    st.write(f"Filtered rows: {filtered_df.shape[0]:,}")
    safe_dataframe(pd.DataFrame({"column": main_df.columns}), use_container_width=True, hide_index=True)

main_tabs = st.tabs([
    "Raw Data",
    "Overview Market Demand",
    "Comparison between Publishes",
    "New | Live update",
    "Check Forecasts on non active SKUs",
    "Sell In per High Level Channels",
])

with main_tabs[0]:
    raw_tabs = st.tabs(["Historical RF", "Allocations", "Opening Stocks FY26"])
    with raw_tabs[0]:
        safe_dataframe(filtered_df.head(1000), use_container_width=True, hide_index=True)
        download_button(filtered_df, "Download filtered historical RF", "historical_rf", "dl_hist")
    with raw_tabs[1]:
        if allocation_df is not None:
            ad = allocation_df.copy()
            if filters.get("pig_code") and "pig_code" in ad.columns:
                ad = ad[ad["pig_code"].astype(str).isin(filters["pig_code"])]
            safe_dataframe(ad.head(1000), use_container_width=True, hide_index=True)
            download_button(ad, "Download allocations", "allocations", "dl_alloc")
        else:
            st.info("Upload Allocation_data.csv to populate this tab.")
    with raw_tabs[2]:
        if pi_df is not None:
            od = pi_df.copy()
            if filters.get("pig_code") and "pig_code" in od.columns:
                od = od[od["pig_code"].astype(str).isin(filters["pig_code"])]
            safe_dataframe(od.head(1000), use_container_width=True, hide_index=True)
            download_button(od, "Download opening stocks", "opening_stocks", "dl_opening")
        else:
            st.info("Upload Set_Up_PI_data.csv to populate this tab.")

with main_tabs[1]:
    overview_df = filtered_df
    available_dims = [c for c in ["brand", "brand_quality", "brand_quality_size", "pig_description", "pig_code", "higher_channel_lst", "customer_groups_channel_lst", "customer_group_name"] if c in overview_df.columns]
    if overview_df.empty:
        st.warning("No data remains after applying the current filters.")
    else:
        analysis_dim = st.radio("Select Dimension", options=available_dims, horizontal=True, key="analysis_dim")
        ov = aggregate_overview(overview_df, analysis_dim, "FY26", "FY25")
        ov_nfy = aggregate_overview(overview_df, analysis_dim, "FY27", "FY26")
        df_long, df_wide = monthly_fy(overview_df)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("FY26 vs FY25 (9LC)", fmt_int(ov["FY26"].sum() - ov["FY25"].sum()))
        with c2:
            denom = ov["FY25"].sum()
            metric_card("FY26 vs FY25 (%)", fmt_pct((ov["FY26"].sum() - ov["FY25"].sum()) / denom if denom else 0))
        with c3:
            metric_card("FY27 vs FY26 (9LC)", fmt_int(ov_nfy["FY27"].sum() - ov_nfy["FY26"].sum()))
        with c4:
            denom = ov_nfy["FY26"].sum()
            metric_card("FY27 vs FY26 (%)", fmt_pct((ov_nfy["FY27"].sum() - ov_nfy["FY26"].sum()) / denom if denom else 0))

        left, right = st.columns([4, 8])
        with left:
            subtabs = st.tabs(["FY26 & FY25", "FY27 & FY26", "FY24 : FY27", "Month-Year", "FY26 vs FY25 | FY27 vs FY26"])
            with subtabs[0]:
                st.plotly_chart(line_chart(df_long, ["FY25", "FY26"], "Monthly Sell IN : FY26 vs FY25"), use_container_width=True, key="ov_1_line")
                st.plotly_chart(variation_bar(df_wide, "FY26", "FY25", "Month Sell IN Variations : FY26 vs FY25"), use_container_width=True, key="ov_1_bar")
            with subtabs[1]:
                st.plotly_chart(line_chart(df_long, ["FY26", "FY27"], "Monthly Sell IN : FY27 vs FY26"), use_container_width=True, key="ov_2_line")
                st.plotly_chart(variation_bar(df_wide, "FY27", "FY26", "Month Sell IN Variations : FY27 vs FY26"), use_container_width=True, key="ov_2_bar")
            with subtabs[2]:
                st.plotly_chart(line_chart(df_long, FY_ORDER, "Monthly Sell IN : FY24 to FY27"), use_container_width=True, key="ov_3_line")
                st.plotly_chart(quarterly_chart(df_long), use_container_width=True, key="ov_3_bar")
            with subtabs[3]:
                xcol = "period" if "period" in overview_df.columns else "calendar_month_abb"
                fig = px.line(overview_df.sort_values(["fiscal_year", "calendar_month_abb"]), x=xcol, y="Publish.Dimension", color="fiscal_year", title="Sell IN by Month-Year")
                fig.update_layout(height=330, margin=dict(l=10, r=10, t=45, b=10), legend_title=None)
                fig.update_yaxes(title="in 9LC units")
                fig.update_xaxes(title="")
                st.plotly_chart(fig, use_container_width=True, key="ov_4_line")
            with subtabs[4]:
                st.plotly_chart(line_chart(df_long, ["FY25", "FY26"], "Monthly Sell IN : FY26 vs FY25"), use_container_width=True, key="ov_5_line_1")
                st.plotly_chart(line_chart(df_long, ["FY26", "FY27"], "Monthly Sell IN : FY27 vs FY26"), use_container_width=True, key="ov_5_line_2")

        with right:
            table_tabs = st.tabs(["FY26 vs FY25", "FY27 vs FY26", "FY26 vs FY25 | PIG code x Description"])
            with table_tabs[0]:
                st.caption("in 9L cases")
                styled_metric_table(ov, "FY26 vs FY25", "FY26.pc", "ov_table_1")
                download_button(ov, "Download FY26 vs FY25", "react_current_RF_data", "dl_ov1")
            with table_tabs[1]:
                st.caption("in 9L cases")
                styled_metric_table(ov_nfy, "FY27 vs FY26", "FY27.pc", "ov_table_2")
                download_button(ov_nfy, "Download FY27 vs FY26", "react_current_RF_NFY_vs_CFY_data", "dl_ov2")
            with table_tabs[2]:
                if {"pig_code", "pig_description"}.issubset(overview_df.columns):
                    pig_df = aggregate_overview(overview_df, "pig_code", "FY26", "FY25")
                    pig_desc = overview_df[["pig_code", "pig_description"]].dropna().drop_duplicates().astype(str)
                    pig_df = pig_df.merge(pig_desc, left_on="Dimension", right_on="pig_code", how="left")
                    show = pig_df[["pig_code", "pig_description", "FY24", "FY25", "FY26", "FY27", "FY26.pc", "delta", "delta.pc"]].copy()
                    safe_dataframe(show.head(1000), use_container_width=True, hide_index=True)
                    download_button(show, "Download PIG code x Description", "react_current_RF_PIG_Description_data", "dl_ov3")
                else:
                    st.info("Required columns for PIG code x Description are not available.")

with main_tabs[2]:
    available_dims = [c for c in ["brand", "brand_quality", "brand_quality_size", "pig_description", "pig_code", "higher_channel_lst", "customer_groups_channel_lst", "customer_group_name"] if c in main_df.columns]
    comparison_dim = st.radio("Select Comparison Dimension", available_dims, horizontal=True, key="comparison_dim")
    diff, monthly = compare_publishes(main_df, filters, old_publish, new_publish, date_range_tuple, comparison_dim)

    c1, c2 = st.columns([5, 7])
    with c1:
        delta_total = monthly["delta"].sum()
        pct_total = delta_total / monthly["old_value"].sum() if monthly["old_value"].sum() else 0
        metric_card(f"{new_publish} vs {old_publish} (9LC)", fmt_int(delta_total))
        metric_card(f"{new_publish} vs {old_publish} (%)", fmt_pct(pct_total))
        comparison_charts(monthly, old_publish, new_publish, "cmp")
    with c2:
        subtabs = st.tabs(["by Dimension", "PIG code x Customer Group", "PIG code x Description"])
        with subtabs[0]:
            show = diff.rename(columns={"Dimension": comparison_dim, "old_value": old_publish, "new_value": new_publish, "delta": f"{new_publish} - {old_publish}", "delta.pc": "delta %"})
            safe_dataframe(show.head(1000), use_container_width=True, hide_index=True)
            download_button(show, "Download by dimension", "react_Demand_Variations_data", "dl_cmp1")
        with subtabs[1]:
            if {"pig_code", "customer_group_name"}.issubset(main_df.columns):
                old_df = apply_filters(main_df, filters, old_publish, None, date_range_tuple)
                new_df = apply_filters(main_df, filters, new_publish, None, date_range_tuple)
                old_g = old_df.groupby(["pig_code", "customer_group_name"], as_index=False)["Publish.Dimension"].sum().rename(columns={"Publish.Dimension": old_publish})
                new_g = new_df.groupby(["pig_code", "customer_group_name"], as_index=False)["Publish.Dimension"].sum().rename(columns={"Publish.Dimension": new_publish})
                pg = old_g.merge(new_g, on=["pig_code", "customer_group_name"], how="outer").fillna(0)
                pg["delta"] = pg[new_publish] - pg[old_publish]
                pg["delta.pc"] = (pg["delta"] / pg[old_publish].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0)
                safe_dataframe(pg.head(1000), use_container_width=True, hide_index=True)
                download_button(pg, "Download PIG x Customer Group", "react_Demand_Variations_PIG_x_CustomerGroup_data", "dl_cmp2")
        with subtabs[2]:
            if {"pig_code", "pig_description"}.issubset(main_df.columns):
                old_df = apply_filters(main_df, filters, old_publish, None, date_range_tuple)
                new_df = apply_filters(main_df, filters, new_publish, None, date_range_tuple)
                old_g = old_df.groupby(["pig_code", "pig_description"], as_index=False)["Publish.Dimension"].sum().rename(columns={"Publish.Dimension": old_publish})
                new_g = new_df.groupby(["pig_code", "pig_description"], as_index=False)["Publish.Dimension"].sum().rename(columns={"Publish.Dimension": new_publish})
                pg = old_g.merge(new_g, on=["pig_code", "pig_description"], how="outer").fillna(0)
                pg["delta"] = pg[new_publish] - pg[old_publish]
                pg["delta.pc"] = (pg["delta"] / pg[old_publish].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0)
                safe_dataframe(pg.head(1000), use_container_width=True, hide_index=True)
                download_button(pg, "Download PIG x Description", "react_Demand_Variations_PIG_x_Description_data", "dl_cmp3")

with main_tabs[3]:
    st.markdown("Regular check of items to be updated")
    st.caption("moving from Status New to Status Live if actual sales happened more than 18 months ago")
    live_df = filtered_df.copy()
    if {"period", "pig_code", "pig_description"}.issubset(live_df.columns):
        status_col = "CentralStatus" if "CentralStatus" in live_df.columns else None
        if status_col is None:
            st.info("CentralStatus column is required for this tab.")
        else:
            grp = live_df.groupby(["pig_code", "pig_description", status_col], as_index=False)["period"].max()
            threshold_ts = pd.to_datetime(threshold)
            grp["suggested_status"] = np.where(grp["period"] <= threshold_ts, "Live", grp[status_col])
            grp = grp[grp[status_col].astype(str).str.lower().eq("new") & grp["suggested_status"].eq("Live")]
            safe_dataframe(grp.head(1000), use_container_width=True, hide_index=True)
            download_button(grp, "Download status change candidates", "react_status_change_data", "dl_live")

with main_tabs[4]:
    st.markdown("Overview Total Sell IN Forecasts")
    st.caption("by Central Status")
    chk = filtered_df.copy()
    status_col = "CentralStatus" if "CentralStatus" in chk.columns else None
    if status_col:
        overview = chk.groupby(status_col, as_index=False)["Publish.Dimension"].sum().rename(columns={"Publish.Dimension": "sell_in"})
        safe_dataframe(overview, use_container_width=True, hide_index=True)
        inactive = chk[chk[status_col].astype(str).str.lower().isin(["dead", "delisted"])]
        if not inactive.empty:
            detail = inactive.groupby(["pig_code", "pig_description", "calendar_month_abb"], as_index=False)["Publish.Dimension"].sum()
            st.markdown("Details monthly Sell IN Forecasts by PIG code")
            safe_dataframe(detail.head(1000), use_container_width=True, hide_index=True)
            download_button(detail, "Download inactive SKU details", "react_check_forecasts_active_skus_data", "dl_inactive")
        else:
            st.info("No dead or delisted SKUs with forecast found under the current filters.")
    else:
        st.info("CentralStatus column was not found in the dataset.")

with main_tabs[5]:
    st.markdown("Total Sell IN Forecasts per High Level Channels")
    hl = filtered_df.copy()
    if "higher_channel_lst" in hl.columns:
        total = hl.groupby("higher_channel_lst", as_index=False)["Publish.Dimension"].sum().rename(columns={"Publish.Dimension": "Total Sell IN"})
        safe_dataframe(total, use_container_width=True, hide_index=True)
        monthly = hl.groupby(["higher_channel_lst", "calendar_month_abb"], as_index=False)["Publish.Dimension"].sum()
        wide = monthly.pivot(index="higher_channel_lst", columns="calendar_month_abb", values="Publish.Dimension").reset_index()
        for m in MONTH_ORDER:
            if m not in wide.columns:
                wide[m] = 0
        wide = wide[["higher_channel_lst"] + MONTH_ORDER]
        st.markdown("Monthly Sell IN Forecasts")
        safe_dataframe(wide.head(1000), use_container_width=True, hide_index=True)
        download_button(wide, "Download channel monthly table", "react_high_level_sell_in_data", "dl_channel1")

        by_month = hl.groupby("calendar_month_abb", as_index=False)["Publish.Dimension"].sum().sort_values("calendar_month_abb")
        st.markdown("Monthly Sell IN Forecasts | to fill up the CTS dashboard")
        safe_dataframe(by_month, use_container_width=True, hide_index=True)
        download_button(by_month, "Download month table", "react_month_abb_sell_in_data", "dl_channel2")
    else:
        st.info("higher_channel_lst column was not found in the dataset.")
