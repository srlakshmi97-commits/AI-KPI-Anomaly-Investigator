import pandas as pd


# ============================================================
# DETECTOR EVALUATION
# ============================================================

# Load the original dataset
data_file = "data/synthetic_incidents.csv"

df = pd.read_csv(data_file)


# ------------------------------------------------------------
# Ground truth
#
# "Normal" = no anomaly
# Anything else = anomaly
# ------------------------------------------------------------

df["ground_truth_anomaly"] = (
    df["synthetic_anomaly_type"] != "Normal"
)


# ------------------------------------------------------------
# Load detector results
# ------------------------------------------------------------

results_file = "data/anomaly_results.xlsx"

results = pd.read_excel(results_file)


# ------------------------------------------------------------
# Create a list of incidents detected by our engine
# ------------------------------------------------------------

detected_incidents = set(
    results["incident_id"]
)


df["detector_anomaly"] = (
    df["incident_id"].isin(
        detected_incidents
    )
)


# ============================================================
# CONFUSION MATRIX
# ============================================================

true_positive = (
    (df["ground_truth_anomaly"] == True)
    &
    (df["detector_anomaly"] == True)
).sum()


false_positive = (
    (df["ground_truth_anomaly"] == False)
    &
    (df["detector_anomaly"] == True)
).sum()


false_negative = (
    (df["ground_truth_anomaly"] == True)
    &
    (df["detector_anomaly"] == False)
).sum()


true_negative = (
    (df["ground_truth_anomaly"] == False)
    &
    (df["detector_anomaly"] == False)
).sum()


# ============================================================
# METRICS
# ============================================================

if true_positive + false_positive > 0:

    precision = (
        true_positive
        /
        (true_positive + false_positive)
    )

else:

    precision = 0


if true_positive + false_negative > 0:

    recall = (
        true_positive
        /
        (true_positive + false_negative)
    )

else:

    recall = 0


if precision + recall > 0:

    f1_score = (
        2
        *
        precision
        *
        recall
        /
        (precision + recall)
    )

else:

    f1_score = 0


accuracy = (
    true_positive + true_negative
) / len(df)


# ============================================================
# PRINT RESULTS
# ============================================================

print()
print("=" * 65)

print("AI KPI / SLA ANOMALY DETECTOR")
print("MODEL EVALUATION")

print("=" * 65)

print()

print(f"Total records:       {len(df)}")

print(
    f"Actual anomalies:    "
    f"{df['ground_truth_anomaly'].sum()}"
)

print(
    f"Detected anomalies:  "
    f"{df['detector_anomaly'].sum()}"
)

print()

print("CONFUSION MATRIX")

print("-" * 40)

print(
    f"True Positives:      {true_positive}"
)

print(
    f"False Positives:     {false_positive}"
)

print(
    f"False Negatives:     {false_negative}"
)

print(
    f"True Negatives:      {true_negative}"
)

print()

print("PERFORMANCE")

print("-" * 40)

print(
    f"Precision:           {precision:.2%}"
)

print(
    f"Recall:              {recall:.2%}"
)

print(
    f"F1 Score:            {f1_score:.2%}"
)

print(
    f"Accuracy:            {accuracy:.2%}"
)

print()

print("=" * 65)

print("Evaluation complete!")

print("=" * 65)