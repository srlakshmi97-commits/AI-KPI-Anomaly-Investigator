import pandas as pd


# ============================================================
# FIND MISSED ANOMALIES
# ============================================================

# Load ground truth
ground_truth = pd.read_csv(
    "data/evaluation_ground_truth.csv"
)


# Load detector results
results = pd.read_excel(
    "data/anomaly_results.xlsx"
)


# ------------------------------------------------------------
# Ground truth anomaly IDs
# ------------------------------------------------------------

actual_anomalies = ground_truth[
    ground_truth["synthetic_anomaly_type"] != "Normal"
]


actual_ids = set(
    actual_anomalies["incident_id"]
)


# ------------------------------------------------------------
# Detector anomaly IDs
# ------------------------------------------------------------

detected_ids = set(
    results["incident_id"]
)


# ------------------------------------------------------------
# Find false negatives
# ------------------------------------------------------------

missed_ids = actual_ids - detected_ids


# ------------------------------------------------------------
# Display missed incidents
# ------------------------------------------------------------

print()
print("=" * 70)

print("MISSED ANOMALIES")

print("=" * 70)

print()

print(
    f"Number of missed anomalies: {len(missed_ids)}"
)

print()


# ------------------------------------------------------------
# Load original dataset
# ------------------------------------------------------------

df = pd.read_csv(
    "data/synthetic_incidents.csv"
)


missed = df[
    df["incident_id"].isin(missed_ids)
]


# ------------------------------------------------------------
# Display useful fields
# ------------------------------------------------------------

columns_to_show = [
    "incident_id",
    "customer",
    "segment",
    "priority_initial",
    "priority_final",
    "priority_changed",
    "priority_change_time",
    "created_at",
    "first_response_at",
    "initial_solution_at",
    "resolved_at",
    "reported_ist_hours",
    "synthetic_anomaly_type"
]


print(
    missed[columns_to_show].to_string(
        index=False
    )
)


print()

print("=" * 70)