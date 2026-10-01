import os
import sys
import subprocess
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
st.set_page_config(
    page_title="AI KPI / SLA Anomaly Investigator",
    page_icon="🔎",
    layout="wide",
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DETECTOR = ROOT / "src" / "anomaly_detector.py"

DEFAULT_DATA = DATA_DIR / "synthetic_incidents.csv"
DEFAULT_RESULTS = DATA_DIR / "anomaly_results.xlsx"

# ------------------------------------------------------------
# STYLE
# ------------------------------------------------------------
st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    .hero {
        padding: 1.4rem 1.6rem;
        border: 1px solid #303642;
        border-radius: 14px;
        background: linear-gradient(135deg, #171a22, #111319);
        margin-bottom: 1.2rem;
    }
    .hero h1 {margin: 0 0 .35rem 0; font-size: 2rem;}
    .hero p {margin: 0; color: #aab2c0;}
    .metric-card {
        padding: 1rem 1.1rem;
        border: 1px solid #303642;
        border-radius: 12px;
        background: #151821;
        min-height: 105px;
    }
    .metric-label {color:#9ca6b5; font-size:.82rem; text-transform:uppercase;}
    .metric-value {font-size:1.8rem; font-weight:700; margin-top:.3rem;}
    .anomaly-box {
        padding: 1rem 1.1rem;
        border-left: 4px solid #ff4b4b;
        background: #151821;
        border-radius: 8px;
        margin: .5rem 0 1rem 0;
    }
    .sla-pass {
        padding: 1rem;
        border: 1px solid #355c45;
        background: #132019;
        border-radius: 10px;
    }
    .sla-miss {
        padding: 1rem;
        border: 1px solid #6c3636;
        background: #211517;
        border-radius: 10px;
    }
    .tag {
        display:inline-block;
        padding:.35rem .65rem;
        border:1px solid #454d5d;
        border-radius:999px;
        background:#202532;
        font-weight:600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def first_existing(df, names):
    for name in names:
        if name in df.columns:
            return name
    return None


def numeric_value(row, names):
    col = first_existing(row.to_frame().T, names)
    if col is None:
        return None
    value = row.get(col)
    if pd.isna(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def text_value(row, names, default="—"):
    col = first_existing(row.to_frame().T, names)
    if col is None:
        return default
    value = row.get(col)
    if pd.isna(value) or str(value).strip() == "":
        return default
    return str(value)


def priority_rank(value):
    try:
        return int(str(value).upper().replace("P", "").strip())
    except Exception:
        return 99


def highest_priority_from_row(row):
    # Prefer the detector's authoritative field.
    value = text_value(
        row,
        [
            "highest_priority_reached",
            "highest_priority",
            "priority_highest",
        ],
        default="",
    )
    if value:
        return value.upper()

    # Fall back to all priority fields present in the record.
    candidates = []
    for col in ["priority_initial", "priority_final", "priority", "initial_priority", "final_priority"]:
        if col in row.index and pd.notna(row[col]):
            value = str(row[col]).upper().strip()
            if value in {"P1", "P2", "P3", "P4"}:
                candidates.append(value)

    if candidates:
        return sorted(candidates, key=priority_rank)[0]
    return "—"


def sla_limits(priority):
    p = str(priority).upper()
    if p in {"P1", "P2"}:
        return 0.25, 4.0  # 15 minutes, 4 hours
    if p in {"P3", "P4"}:
        return 0.50, 8.0  # 30 minutes, 8 hours
    return None, None


def get_metric(row, kind):
    if kind == "response":
        return numeric_value(
            row,
            [
                "response_time_hours",
                "initial_response_time_hours",
                "response_hours",
            ],
        )

    if kind == "ist":
        return numeric_value(
            row,
            [
                "calculated_ist_hours",
                "initial_solution_time_hours",
                "ist_hours",
            ],
        )

    if kind == "reported_ist":
        return numeric_value(row, ["reported_ist_hours", "reported_ist"])

    if kind == "resolution":
        return numeric_value(
            row,
            [
                "resolution_time_hours",
                "resolution_hours",
            ],
        )

    return None


def fmt_hours(value):
    if value is None:
        return "—"
    return f"{value:.2f} hrs"


def fmt_response(value):
    if value is None:
        return "—"
    minutes = value * 60
    if abs(minutes) < 60:
        return f"{minutes:.0f} min"
    return f"{value:.2f} hrs"


def compute_sla(row):
    priority = highest_priority_from_row(row)
    response_limit, ist_limit = sla_limits(priority)

    response = get_metric(row, "response")
    ist = get_metric(row, "ist")

    if response_limit is None:
        return {
            "status": "Unavailable",
            "response_miss": False,
            "ist_miss": False,
            "reason": "No valid P1–P4 priority is available.",
            "response_limit": None,
            "ist_limit": None,
        }

    response_miss = response is not None and response > response_limit
    ist_miss = ist is not None and ist > ist_limit

    if response_miss and ist_miss:
        reason = "Both Initial Response and Initial Solution Time exceeded the SLA limits."
    elif response_miss:
        reason = "Initial Response exceeded the SLA limit."
    elif ist_miss:
        reason = "Initial Solution Time exceeded the SLA limit."
    elif response is None or ist is None:
        reason = "The required SLA metric is unavailable."
    else:
        reason = "Initial Response and Initial Solution Time are within SLA."

    return {
        "status": "Missed" if response_miss or ist_miss else "Met",
        "response_miss": response_miss,
        "ist_miss": ist_miss,
        "reason": reason,
        "response_limit": response_limit,
        "ist_limit": ist_limit,
    }


def run_detector_on_upload(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        (tmp_root / "src").mkdir()
        (tmp_root / "data").mkdir()

        detector_copy = tmp_root / "src" / "anomaly_detector.py"
        detector_copy.write_text(DETECTOR.read_text(encoding="utf-8"), encoding="utf-8")

        if suffix == ".csv":
            uploaded_file.seek(0)
            source = pd.read_csv(uploaded_file)
        else:
            uploaded_file.seek(0)
            source = pd.read_excel(uploaded_file)

        source.to_csv(tmp_root / "data" / "synthetic_incidents.csv", index=False)

        result = subprocess.run(
            [sys.executable, str(detector_copy)],
            cwd=str(tmp_root),
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr or result.stdout or "Detector failed.")

        results_path = tmp_root / "data" / "anomaly_results.xlsx"
        if not results_path.exists():
            raise RuntimeError("Detector completed but anomaly_results.xlsx was not created.")

        results = pd.read_excel(results_path)
        return source, results


def load_demo():
    source = pd.read_csv(DEFAULT_DATA)
    results = pd.read_excel(DEFAULT_RESULTS)
    return source, results


def combine(source, results):
    if "incident_id" not in source.columns or "incident_id" not in results.columns:
        raise ValueError("The dataset must contain an incident_id column.")

    # Keep the original uploaded/source fields intact. The detector output
    # repeats many source columns (customer, reported IST, priority fields,
    # timestamps), so merging all of them creates pandas _x/_y columns and
    # hides the values from the dashboard. Only bring in detector-derived
    # fields that are not already present in the source dataset.
    detector_only_cols = [
        c for c in results.columns
        if c != "incident_id" and c not in source.columns
    ]

    merged = source.merge(
        results[["incident_id"] + detector_only_cols],
        on="incident_id",
        how="left",
    )

    # The detector writes anomaly rows only. Everything not present is normal.
    merged["anomaly_detected"] = merged["incident_id"].isin(
        results["incident_id"]
    )

    if "anomaly_category" not in merged.columns:
        merged["anomaly_category"] = ""
    merged["anomaly_category"] = merged["anomaly_category"].fillna("")

    return merged


def get_explanation_cache():
    path = DATA_DIR / "ai_explanations.xlsx"
    if not path.exists():
        return {}
    try:
        df = pd.read_excel(path)
        if "incident_id" not in df.columns:
            return {}
        text_col = first_existing(df, ["explanation", "ai_explanation"])
        if not text_col:
            return {}
        return dict(zip(df["incident_id"].astype(str), df[text_col].astype(str)))
    except Exception:
        return {}


def ai_investigate(row):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "OPENAI_API_KEY is not configured in this environment."

    try:
        from openai import OpenAI
    except Exception:
        return "The OpenAI Python package is not installed."

    priority = highest_priority_from_row(row)
    sla = compute_sla(row)

    prompt = f"""
You are an operations analyst investigating a customer incident.

Use only the incident data below. Do not invent facts.

Incident ID: {text_value(row, ['incident_id'])}
Customer: {text_value(row, ['customer', 'customer_name'])}
Highest Priority Reached: {priority}
Final Priority: {text_value(row, ['priority_final', 'final_priority'])}
Response Time: {fmt_response(get_metric(row, 'response'))}
Initial Solution Time (calculated): {fmt_hours(get_metric(row, 'ist'))}
Reported IST: {fmt_hours(get_metric(row, 'reported_ist'))}
Resolution Time: {fmt_hours(get_metric(row, 'resolution'))}
Anomaly Category: {text_value(row, ['anomaly_category'])}
Anomaly Reason: {text_value(row, ['anomaly_reason'])}

SLA:
- P1/P2: Initial Response <= 15 minutes; IST <= 4 hours
- P3/P4: Initial Response <= 30 minutes; IST <= 8 hours
- SLA priority is the highest priority reached.
- If an incident is upgraded before first response, response timing begins at the upgrade.
- If an incident is upgraded before initial solution, IST timing begins at the upgrade.
- IST ends at initial_solution_at, not incident closure.

SLA status: {sla['status']}
SLA finding: {sla['reason']}

Return exactly these four sections:
1. What happened
2. Why it was flagged
3. Business impact
4. What should be investigated next
"""

    client = OpenAI(api_key=api_key)
    response = client.responses.create(
        model="gpt-5.6-luna",
        input=prompt,
    )
    return response.output_text


# ------------------------------------------------------------
# LOAD DATA
# ------------------------------------------------------------
st.markdown(
    """
    <div class="hero">
        <h1>🔎 AI KPI / SLA Anomaly Investigator</h1>
        <p>Upload incident data → validate KPI/SLA performance → investigate anomalies → use AI to explain the finding.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("📁 Data Source")
    uploaded = st.file_uploader(
        "Upload incident data",
        type=["csv", "xlsx"],
        help="Upload an exported incident/case dataset.",
    )

    st.divider()
    st.header("🔍 Investigation Filters")

    source_label = "Demo dataset"
    if uploaded is not None:
        source_label = uploaded.name

try:
    if uploaded is not None:
        with st.spinner("Running KPI / SLA anomaly detection on uploaded data..."):
            source_df, result_df = run_detector_on_upload(uploaded)
        data = combine(source_df, result_df)
    else:
        source_df, result_df = load_demo()
        data = combine(source_df, result_df)
except Exception as exc:
    st.error(f"Could not load or analyze the data: {exc}")
    st.stop()

categories = ["All"] + sorted(
    [x for x in data.loc[data["anomaly_detected"], "anomaly_category"].dropna().unique() if str(x).strip()]
)

with st.sidebar:
    selected_category = st.selectbox("Anomaly Category", categories)
    st.caption(f"Source: {source_label}")
    st.caption("Rule-based detection + AI-assisted investigation")

# ------------------------------------------------------------
# FILTER
# ------------------------------------------------------------
if selected_category == "All":
    view = data.copy()
else:
    view = data[
        data["anomaly_detected"]
        & (data["anomaly_category"].astype(str) == selected_category)
    ].copy()

anomalies = view[view["anomaly_detected"]].copy()
total_records = len(view)
anomaly_count = len(anomalies)
normal_count = max(total_records - anomaly_count, 0)
anomaly_rate = (anomaly_count / total_records * 100) if total_records else 0

# ------------------------------------------------------------
# OVERVIEW
# ------------------------------------------------------------
st.subheader("📊 Investigation Overview")

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Records</div><div class="metric-value">{total_records:,}</div></div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Detected Anomalies</div><div class="metric-value">{anomaly_count:,}</div></div>',
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Not in Selected Category</div><div class="metric-value">{normal_count:,}</div></div>',
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Anomaly Rate</div><div class="metric-value">{anomaly_rate:.1f}%</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("### Anomaly Landscape")

if anomaly_count:
    breakdown = (
        anomalies["anomaly_category"]
        .value_counts()
        .rename_axis("Category")
        .reset_index(name="Incidents")
    )
    st.dataframe(breakdown, use_container_width=True, hide_index=True)
else:
    st.info("No anomalies match the selected filter.")

# ------------------------------------------------------------
# INVESTIGATION QUEUE
# ------------------------------------------------------------
st.subheader("🚨 Investigation Queue")

if anomaly_count:
    queue_cols = [
        c
        for c in [
            "incident_id",
            "customer",
            "customer_name",
            "anomaly_category",
            "anomaly_reason",
            "highest_priority_reached",
            "priority_final",
        ]
        if c in anomalies.columns
    ]

    queue = anomalies[queue_cols].copy()

    # Add a normalized highest-priority display if detector column is absent.
    if "highest_priority_reached" not in queue.columns:
        queue["highest_priority_reached"] = anomalies.apply(highest_priority_from_row, axis=1)

    display_names = {
        "incident_id": "Incident",
        "customer": "Customer",
        "customer_name": "Customer",
        "anomaly_category": "Anomaly Category",
        "anomaly_reason": "Why Flagged",
        "highest_priority_reached": "Highest Priority",
        "priority_final": "Final Priority",
    }
    queue = queue.rename(columns=display_names)

    st.dataframe(
        queue,
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("The investigation queue is empty for this filter.")

# ------------------------------------------------------------
# INCIDENT INVESTIGATION
# ------------------------------------------------------------
st.subheader("🔬 Incident Investigation")

if anomaly_count:
    incident_ids = anomalies["incident_id"].astype(str).tolist()
    selected_incident = st.selectbox("Select an incident", incident_ids)

    row = anomalies[anomalies["incident_id"].astype(str) == selected_incident].iloc[0]

    st.markdown(
        f"""
        <div class="anomaly-box">
            <h3 style="margin:0;">{selected_incident}</h3>
            <div style="color:#aab2c0;margin-top:.35rem;">
                Customer: {text_value(row, ['customer', 'customer_name'])}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    priority = highest_priority_from_row(row)
    response = get_metric(row, "response")
    ist = get_metric(row, "ist")
    resolution = get_metric(row, "resolution")
    category = text_value(row, ["anomaly_category"])

    m1, m2, m3, m4 = st.columns(4)

    with m1:
        st.metric("Highest Priority Reached", priority)

    with m2:
        st.metric("Initial Response", fmt_response(response))

    with m3:
        st.metric("Initial Solution Time", fmt_hours(ist))

    with m4:
        st.metric("Resolution Time", fmt_hours(resolution))

    st.markdown("### 🚨 SLA Investigation")

    sla = compute_sla(row)

    if sla["status"] == "Missed":
        st.markdown(
            f"""
            <div class="sla-miss">
                <strong>⚠️ SLA MISSED</strong><br><br>
                {sla["reason"]}
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif sla["status"] == "Met":
        st.markdown(
            f"""
            <div class="sla-pass">
                <strong>✅ SLA MET</strong><br><br>
                {sla["reason"]}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.info(sla["reason"])

    if sla["response_limit"] is not None:
        st.caption(
            f"SLA rules for {priority}: "
            f"Initial Response ≤ {sla['response_limit'] * 60:.0f} min | "
            f"Initial Solution Time ≤ {sla['ist_limit']:.0f} hrs. "
            f"The SLA priority is the highest priority reached."
        )

    st.markdown("### Why was this incident flagged?")

    reason = text_value(row, ["anomaly_reason"], "No detector reason available.")
    st.markdown(
        f'<div class="anomaly-box">{reason}</div>',
        unsafe_allow_html=True,
    )

    # KPI details only for KPI Calculation anomalies.
    if category == "KPI Calculation":
        st.markdown("### 📐 KPI Investigation Details")

        reported = get_metric(row, "reported_ist")
        calculated = get_metric(row, "ist")
        variance = numeric_value(
            row,
            ["ist_difference_hours", "ist_variance_hours", "ist_variance"],
        )

        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("Reported IST", fmt_hours(reported))
        with k2:
            st.metric("Calculated IST", fmt_hours(calculated))
        with k3:
            st.metric("IST Variance", fmt_hours(variance))

    st.markdown("### 🤖 AI Investigation")

    cache = get_explanation_cache()
    cached = cache.get(str(selected_incident))

    if cached and cached != "nan":
        with st.expander("View existing AI investigation", expanded=True):
            st.write(cached)

    if st.button(
        "🤖 Investigate This Incident with AI",
        type="primary",
        use_container_width=True,
    ):
        with st.spinner("AI is investigating the incident..."):
            try:
                explanation = ai_investigate(row)
                st.markdown(
                    '<div class="anomaly-box"><strong>AI Investigation Result</strong></div>',
                    unsafe_allow_html=True,
                )
                st.write(explanation)
            except Exception as exc:
                st.error(f"AI investigation failed: {exc}")

else:
    st.info("Select a category with anomalies to investigate an incident.")

# ------------------------------------------------------------
# COMPLETE DATASET
# ------------------------------------------------------------
st.subheader("📂 Complete Dataset")

with st.expander(f"View all {len(data):,} analyzed incidents"):
    st.dataframe(data, use_container_width=True, hide_index=True)
