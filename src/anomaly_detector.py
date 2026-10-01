import pandas as pd
import numpy as np


# ============================================================
# AI KPI / SLA ANOMALY INVESTIGATOR
# Version 3
# ============================================================


# ============================================================
# 1. LOAD DATA
# ============================================================

file_path = "data/synthetic_incidents.csv"

df = pd.read_csv(file_path)


# ============================================================
# 2. CONVERT TIMESTAMPS
# ============================================================

timestamp_columns = [
    "created_at",
    "priority_change_time",
    "first_response_at",
    "initial_solution_at",
    "resolved_at"
]

for column in timestamp_columns:

    df[column] = pd.to_datetime(
        df[column],
        errors="coerce"
    )


# ============================================================
# 3. DETERMINE HIGHEST PRIORITY REACHED
# ============================================================

# Priority hierarchy: P1 is highest severity.
priority_rank = {
    "P1": 1,
    "P2": 2,
    "P3": 3,
    "P4": 4
}

df["priority_initial"] = (
    df["priority_initial"]
    .astype(str)
    .str.strip()
    .str.upper()
)

df["priority_final"] = (
    df["priority_final"]
    .astype(str)
    .str.strip()
    .str.upper()
)

df["highest_priority_reached"] = df.apply(
    lambda row: min(
        [
            p for p in [
                row["priority_initial"],
                row["priority_final"]
            ]
            if p in priority_rank
        ],
        key=lambda p: priority_rank[p]
    ) if any(
        p in priority_rank for p in [
            row["priority_initial"],
            row["priority_final"]
        ]
    ) else np.nan,
    axis=1
)


# ============================================================
# 3A. DETERMINE THE RESPONSE / IST CLOCK START
# ============================================================

# If the incident was upgraded from P3/P4 to P1/P2 before the first
# response, the response and IST clocks begin at the upgrade timestamp.
#
# If the highest priority was already present when the incident was
# created, the clocks begin at incident creation.
#
# A later downgrade does not change the highest priority reached.

initial_rank = df["priority_initial"].map(priority_rank)
highest_rank = df["highest_priority_reached"].map(priority_rank)

upgraded_to_higher_priority = (
    initial_rank.notna()
    & highest_rank.notna()
    & (highest_rank < initial_rank)
)

upgrade_before_response = (
    upgraded_to_higher_priority
    & df["priority_change_time"].notna()
    & df["first_response_at"].notna()
    & (df["priority_change_time"] <= df["first_response_at"])
)

upgrade_before_solution = (
    upgraded_to_higher_priority
    & df["priority_change_time"].notna()
    & df["initial_solution_at"].notna()
    & (df["priority_change_time"] <= df["initial_solution_at"])
)

df["response_clock_start"] = df["created_at"]

df.loc[
    upgrade_before_response,
    "response_clock_start"
] = df.loc[
    upgrade_before_response,
    "priority_change_time"
]

df["ist_clock_start"] = df["created_at"]

df.loc[
    upgrade_before_solution,
    "ist_clock_start"
] = df.loc[
    upgrade_before_solution,
    "priority_change_time"
]


# ============================================================
# 3B. CALCULATE INITIAL RESPONSE TIME
# ============================================================

df["response_time_hours"] = (
    df["first_response_at"]
    - df["response_clock_start"]
).dt.total_seconds() / 3600


# ============================================================
# 4. CALCULATE RESOLUTION TIME
# ============================================================

df["resolution_time_hours"] = (
    df["resolved_at"]
    - df["created_at"]
).dt.total_seconds() / 3600


df["response_time_hours"] = df[
    "response_time_hours"
].round(2)


df["resolution_time_hours"] = df[
    "resolution_time_hours"
].round(2)


# ============================================================
# 5. CREATE OUTPUT COLUMNS
# ============================================================

df["calculated_ist_hours"] = np.nan

df["ist_difference_hours"] = np.nan

df["response_sla_limit_minutes"] = np.nan

df["ist_sla_limit_hours"] = np.nan

df["response_sla_miss"] = False

df["ist_sla_miss"] = False

df["sla_miss"] = False

df["data_quality_issue"] = False

df["business_rule_violation"] = False

df["operational_anomaly"] = False

df["anomaly_detected"] = False

df["anomaly_category"] = ""

df["anomaly_reason"] = ""


# ============================================================
# RULE 1
# BUSINESS-RULE IST CALCULATION / KPI VALIDATION
# ============================================================

# IST is always measured to the INITIAL SOLUTION timestamp.
# It is never calculated using the final resolution timestamp.
#
# For P3/P4 -> P1/P2 upgrades, the IST clock begins at the upgrade
# timestamp when that upgrade occurred before the initial solution.

valid_ist = (
    df["ist_clock_start"].notna()
    & df["initial_solution_at"].notna()
    & (df["initial_solution_at"] >= df["ist_clock_start"])
)

df.loc[
    valid_ist,
    "calculated_ist_hours"
] = (
    (
        df.loc[
            valid_ist,
            "initial_solution_at"
        ]
        -
        df.loc[
            valid_ist,
            "ist_clock_start"
        ]
    )
    .dt.total_seconds()
    / 3600
)

df.loc[
    valid_ist,
    "calculated_ist_hours"
] = df.loc[
    valid_ist,
    "calculated_ist_hours"
].round(2)


# ------------------------------------------------------------
# Compare reported vs calculated IST
# ------------------------------------------------------------

valid_reported_ist = (
    valid_ist
    & df["reported_ist_hours"].notna()
)

df.loc[
    valid_reported_ist,
    "ist_difference_hours"
] = (
    df.loc[
        valid_reported_ist,
        "reported_ist_hours"
    ]
    -
    df.loc[
        valid_reported_ist,
        "calculated_ist_hours"
    ]
)

df.loc[
    valid_reported_ist,
    "ist_difference_hours"
] = df.loc[
    valid_reported_ist,
    "ist_difference_hours"
].round(2)


# ------------------------------------------------------------
# Detect meaningful KPI discrepancy
# ------------------------------------------------------------

ist_error = (
    valid_reported_ist
    &
    (
        df["ist_difference_hours"].abs() > 0.25
    )
)

df.loc[
    ist_error,
    "business_rule_violation"
] = True

df.loc[
    ist_error,
    "anomaly_detected"
] = True

df.loc[
    ist_error,
    "anomaly_category"
] = "KPI Calculation"

df.loc[
    ist_error,
    "anomaly_reason"
] = (
    "Reported IST differs from the business-rule calculation. "
    "IST is calculated from the applicable response/solution clock start "
    "to the initial-solution timestamp. If the incident was upgraded "
    "from P3/P4 to P1/P2 before initial solution, the clock begins at "
    "the priority escalation timestamp."
)


# ============================================================
# RULE 2
# PRIORITY-SPECIFIC SLA / OPERATIONAL PERFORMANCE
# ============================================================

# Response SLA:
# P1/P2 <= 15 minutes
# P3/P4 <= 30 minutes
#
# IST SLA:
# P1/P2 <= 4 hours
# P3/P4 <= 8 hours
#
# The highest priority reached determines the SLA tier.

is_p1_p2 = df["highest_priority_reached"].isin(["P1", "P2"])
is_p3_p4 = df["highest_priority_reached"].isin(["P3", "P4"])

df.loc[
    is_p1_p2,
    "response_sla_limit_minutes"
] = 15

df.loc[
    is_p3_p4,
    "response_sla_limit_minutes"
] = 30

df.loc[
    is_p1_p2,
    "ist_sla_limit_hours"
] = 4

df.loc[
    is_p3_p4,
    "ist_sla_limit_hours"
] = 8


valid_response_sla = (
    df["response_time_hours"].notna()
    & df["response_sla_limit_minutes"].notna()
    & (df["response_time_hours"] >= 0)
)

valid_ist_sla = (
    df["calculated_ist_hours"].notna()
    & df["ist_sla_limit_hours"].notna()
    & (df["calculated_ist_hours"] >= 0)
)

df.loc[
    valid_response_sla,
    "response_sla_miss"
] = (
    df.loc[
        valid_response_sla,
        "response_time_hours"
    ]
    >
    df.loc[
        valid_response_sla,
        "response_sla_limit_minutes"
    ] / 60
)

df.loc[
    valid_ist_sla,
    "ist_sla_miss"
] = (
    df.loc[
        valid_ist_sla,
        "calculated_ist_hours"
    ]
    >
    df.loc[
        valid_ist_sla,
        "ist_sla_limit_hours"
    ]
)

df["sla_miss"] = (
    df["response_sla_miss"]
    |
    df["ist_sla_miss"]
)

sla_anomaly = df["sla_miss"]

df.loc[
    sla_anomaly,
    "operational_anomaly"
] = True

df.loc[
    sla_anomaly,
    "anomaly_detected"
] = True

df.loc[
    sla_anomaly,
    "anomaly_category"
] = "Operational Performance"


def build_sla_reason(row):
    reasons = []

    if row["response_sla_miss"]:
        reasons.append(
            f"Initial response was {row['response_time_hours'] * 60:.0f} "
            f"minutes against a {row['response_sla_limit_minutes']:.0f}-minute "
            f"SLA for {row['highest_priority_reached']}."
        )

    if row["ist_sla_miss"]:
        reasons.append(
            f"Initial Solution Time was {row['calculated_ist_hours']:.2f} "
            f"hours against a {row['ist_sla_limit_hours']:.0f}-hour SLA "
            f"for {row['highest_priority_reached']}."
        )

    return " ".join(reasons)


df.loc[
    sla_anomaly,
    "anomaly_reason"
] = df.loc[
    sla_anomaly
].apply(
    build_sla_reason,
    axis=1
)


# ============================================================
# RULE 3
# RESOLUTION TIME IS A SEPARATE OPERATIONAL METRIC
# ============================================================

# Resolution time is retained for visibility, but it is NOT used as IST.
# IST ends at initial_solution_at.

# ============================================================
# RULE 3
# RESOLUTION TIME IS A SEPARATE OPERATIONAL METRIC
# ============================================================

# Resolution time is retained for visibility, but it is NOT used as an
# anomaly threshold and it is NOT Initial Solution Time.
#
# IST ends at initial_solution_at.
# Resolution time is created_at -> resolved_at.

# ============================================================
# NO GENERIC RESPONSE / RESOLUTION OUTLIER RULES
# ============================================================

# The application does not use generic thresholds such as:
#   response > 8 hours
#   resolution > 72 hours
#
# Operational anomalies are determined only by the priority-specific
# response and Initial Solution Time SLA rules above.

# ============================================================
# 6. CREATE ANOMALY REPORT
# ============================================================

anomalies = df[
    df["anomaly_detected"] == True
].copy()


# ============================================================
# 7. SORT BY IMPORTANCE
# ============================================================

category_order = {
    "KPI Calculation": 1,
    "Operational Performance": 2
}


anomalies["priority_order"] = (
    anomalies["anomaly_category"]
    .map(category_order)
)


anomalies = anomalies.sort_values(
    by=[
        "priority_order",
        "incident_id"
    ]
)


# ============================================================
# 8. SAVE RESULTS
# ============================================================

output_file = "data/anomaly_results.xlsx"

anomalies.to_excel(
    output_file,
    index=False
)


# ============================================================
# 9. PRINT SUMMARY
# ============================================================

print()

print("=" * 70)

print("AI KPI / SLA ANOMALY INVESTIGATOR")

print("VERSION 4")

print("=" * 70)

print()

print(
    f"Total incidents analyzed: {len(df)}"
)

print(
    f"Potential anomalies detected: "
    f"{len(anomalies)}"
)

print("Highest-priority SLA logic: P1 > P2 > P3 > P4")

print()

print("Detection breakdown:")

print()

print(
    anomalies[
        "anomaly_category"
    ].value_counts()
)

print()

print("=" * 70)

print("Analysis complete!")

print("=" * 70)

print()

print(
    f"Results saved to: {output_file}"
)

print()