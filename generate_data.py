import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta


# ============================================================
# PROJECT CONFIGURATION
# ============================================================

PROJECT_NAME = "EnterpriseNet Services"

NUM_INCIDENTS = 1000

np.random.seed(42)
random.seed(42)


# ============================================================
# FICTIONAL CUSTOMERS
# ============================================================

customers = [
    "Apex Financial",
    "Northstar Health",
    "Meridian Public Services",
    "Vertex Technologies",
    "BluePeak Telecom",
    "Summit Retail",
    "Orion Manufacturing",
    "Pioneer Energy"
]

segments = {
    "Apex Financial": "BFSI",
    "Northstar Health": "Healthcare",
    "Meridian Public Services": "Public Sector",
    "Vertex Technologies": "Technology",
    "BluePeak Telecom": "Telecommunications",
    "Summit Retail": "Retail",
    "Orion Manufacturing": "Manufacturing",
    "Pioneer Energy": "Energy"
}


# ============================================================
# NETWORK DATA
# ============================================================

devices = [
    "Catalyst 9300",
    "Catalyst 9500",
    "ISR Router",
    "Wireless AP",
    "Firewall"
]

locations = [
    "Austin",
    "Denver",
    "Atlanta",
    "Phoenix",
    "Chicago",
    "Boston",
    "Charlotte",
    "Minneapolis",
    "Seattle",
    "Dallas"
]

engineers = [
    "Engineer-01",
    "Engineer-02",
    "Engineer-03",
    "Engineer-04",
    "Engineer-05",
    "Engineer-06",
    "Engineer-07",
    "Engineer-08",
    "Engineer-09",
    "Engineer-10"
]

shifts = [
    "Day",
    "Night"
]

priorities = [
    "P1",
    "P2",
    "P3",
    "P4"
]

status_values = [
    "Open",
    "Investigating",
    "Pending Customer",
    "Escalated",
    "Resolved",
    "Closed"
]


# ============================================================
# INCIDENT DESCRIPTIONS
# ============================================================

descriptions = [
    "Intermittent connectivity reported by customer",
    "Switch rebooting unexpectedly",
    "Network latency observed at site",
    "Wireless connectivity issue",
    "Device unreachable",
    "Packet loss reported",
    "High CPU utilization observed",
    "Interface flapping",
    "Configuration issue suspected",
    "Hardware failure reported",
    "Network performance degradation",
    "Unexpected device restart",
    "Customer unable to access network services",
    "High interface error rate detected"
]



# ============================================================
# SLA / KPI BUSINESS RULES
# ============================================================

# Initial Response SLA
# P1/P2 -> <= 15 minutes
# P3/P4 -> <= 30 minutes
#
# Initial Solution Time (IST) SLA
# P1/P2 -> expected 2-4 hours; SLA limit = 4 hours
# P3/P4 -> expected 4-8 hours; SLA limit = 8 hours
#
# IMPORTANT:
# - The highest priority reached determines the SLA tier.
# - If a P3/P4 incident is upgraded to P1/P2 before first response,
#   the response clock starts at the upgrade timestamp.
# - For IST, if the upgrade happens before initial solution, the IST
#   clock starts at the upgrade timestamp.
# - Resolution time is a separate metric: created_at -> resolved_at.
# - The dataset intentionally contains realistic SLA misses and KPI
#   calculation errors for detector evaluation.

response_sla_minutes = {
    "P1": 15,
    "P2": 15,
    "P3": 30,
    "P4": 30
}

ist_sla_hours = {
    "P1": 4,
    "P2": 4,
    "P3": 8,
    "P4": 8
}

ist_expected_range = {
    "P1": (2, 4),
    "P2": (2, 4),
    "P3": (4, 8),
    "P4": (4, 8)
}

records = []

base_date = datetime(2026, 8, 1)

# Keep the original 170-anomaly evaluation size, but make every anomaly
# represent a business-realistic condition:
#   70 Initial Response SLA misses
#   70 IST SLA misses
#   30 KPI calculation errors
#
# All remaining 830 incidents are normal and satisfy their applicable SLA.
response_miss_ids = set(range(0, 70))
ist_miss_ids = set(range(70, 140))
kpi_error_ids = set(range(140, 170))


# ============================================================
# GENERATE INCIDENTS
# ============================================================

for i in range(NUM_INCIDENTS):

    incident_id = f"INC-{10000 + i}"

    customer = random.choice(customers)
    segment = segments[customer]
    device = random.choice(devices)
    location = random.choice(locations)
    engineer = random.choice(engineers)
    shift = random.choice(shifts)
    status = random.choice(status_values)
    description = random.choice(descriptions)

    customer_impact = random.choice([
        "Low",
        "Medium",
        "High",
        "Critical"
    ])

    # --------------------------------------------------------
    # GROUND-TRUTH ANOMALY TYPE
    # --------------------------------------------------------

    if i in response_miss_ids:
        anomaly_type = "Initial Response SLA Miss"
    elif i in ist_miss_ids:
        anomaly_type = "IST SLA Miss"
    elif i in kpi_error_ids:
        anomaly_type = "KPI Calculation Error"
    else:
        anomaly_type = "Normal"

    # --------------------------------------------------------
    # PRIORITY
    # --------------------------------------------------------

    initial_priority = random.choices(
        priorities,
        weights=[0.05, 0.15, 0.45, 0.35]
    )[0]

    final_priority = initial_priority
    priority_changed = False
    priority_change_time = None

    # About 15% of P3/P4 incidents are upgraded to P1/P2.
    # The upgrade timing is deliberately varied so the detector must
    # determine whether the escalation happened before first response.
    if (
        initial_priority in ["P3", "P4"]
        and random.random() < 0.15
    ):
        final_priority = random.choice(["P1", "P2"])
        priority_changed = True

    # --------------------------------------------------------
    # CREATED TIME
    # --------------------------------------------------------

    created_at = base_date + timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )

    # --------------------------------------------------------
    # PRIORITY TRANSITION TIMING
    # --------------------------------------------------------

    if priority_changed:

        # For most transitions, escalation happens before first response.
        # This lets the dataset exercise the escalation-based response clock.
        # KPI-error transition cases must occur before initial solution so
        # the detector can compare the correct escalation-based IST against
        # the intentionally incorrect reported IST.
        if i in kpi_error_ids:
            upgrade_before_response = True
        else:
            upgrade_before_response = random.random() < 0.70

        if upgrade_before_response:
            if i in kpi_error_ids:
                # Ensure the reported-vs-calculated IST difference exceeds
                # the detector's 0.25-hour materiality threshold.
                upgrade_minutes = random.randint(20, 35)
            else:
                upgrade_minutes = random.randint(5, 20)

            priority_change_time = (
                created_at
                + timedelta(minutes=upgrade_minutes)
            )
        else:
            priority_change_time = (
                created_at
                + timedelta(
                    hours=random.randint(1, 3),
                    minutes=random.randint(0, 30)
                )
            )

    # --------------------------------------------------------
    # DETERMINE HIGHEST PRIORITY REACHED
    # --------------------------------------------------------

    priority_rank = {
        "P1": 1,
        "P2": 2,
        "P3": 3,
        "P4": 4
    }

    highest_priority = min(
        [initial_priority, final_priority],
        key=lambda p: priority_rank[p]
    )

    # --------------------------------------------------------
    # INITIAL RESPONSE
    # --------------------------------------------------------

    response_limit = response_sla_minutes[highest_priority]

    if priority_changed and priority_change_time is not None:
        # Some upgrades occur before response; others after response.
        # We construct the timestamp first and then ensure the resulting
        # relationship is realistic.
        if priority_change_time <= created_at + timedelta(minutes=20):
            if anomaly_type == "Initial Response SLA Miss":
                # Deliberate miss against the P1/P2 or P3/P4 tier.
                response_delay_from_upgrade = random.randint(
                    response_limit + 5,
                    response_limit + 30
                )
            else:
                response_delay_from_upgrade = random.randint(
                    3,
                    max(4, response_limit - 2)
                )

            first_response_at = (
                priority_change_time
                + timedelta(minutes=response_delay_from_upgrade)
            )
        else:
            # Upgrade after first response. Response is measured from creation.
            if anomaly_type == "Initial Response SLA Miss":
                response_delay = random.randint(
                    response_limit + 5,
                    response_limit + 30
                )
            else:
                response_delay = random.randint(
                    5,
                    max(6, response_limit - 2)
                )

            first_response_at = (
                created_at
                + timedelta(minutes=response_delay)
            )
    else:
        if anomaly_type == "Initial Response SLA Miss":
            response_delay = random.randint(
                response_limit + 5,
                response_limit + 30
            )
        else:
            response_delay = random.randint(
                5,
                max(6, response_limit - 2)
            )

        first_response_at = (
            created_at
            + timedelta(minutes=response_delay)
        )

    # --------------------------------------------------------
    # INITIAL SOLUTION / IST
    # --------------------------------------------------------

    if priority_changed and priority_change_time is not None:
        ist_clock_start = (
            priority_change_time
            if priority_change_time <= (
                created_at + timedelta(hours=8)
            )
            else created_at
        )
    else:
        ist_clock_start = created_at

    ist_limit = ist_sla_hours[highest_priority]
    ist_low, ist_high = ist_expected_range[highest_priority]

    if anomaly_type == "IST SLA Miss":
        ist_hours = round(
            random.uniform(
                ist_limit + 0.5,
                ist_limit + 3.0
            ),
            2
        )
    else:
        # Normal and KPI-error incidents are kept within the applicable
        # IST SLA so KPI errors remain distinct from SLA misses.
        ist_hours = round(
            random.uniform(
                max(0.5, ist_low),
                max(ist_low + 0.1, ist_high - 0.25)
            ),
            2
        )

    initial_solution_at = (
        ist_clock_start
        + timedelta(hours=ist_hours)
    )

    calculated_ist_hours = round(
        (
            initial_solution_at - ist_clock_start
        ).total_seconds() / 3600,
        2
    )

    # --------------------------------------------------------
    # SYSTEM-REPORTED IST
    # --------------------------------------------------------

    if anomaly_type == "KPI Calculation Error":
        # Intentionally report the wrong clock basis for an upgrade case
        # when possible. Otherwise introduce a material reporting error.
        if priority_changed:
            reported_ist_hours = round(
                (
                    initial_solution_at - created_at
                ).total_seconds() / 3600,
                2
            )
        else:
            reported_ist_hours = round(
                calculated_ist_hours + random.uniform(0.75, 2.0),
                2
            )
    else:
        reported_ist_hours = calculated_ist_hours

    # --------------------------------------------------------
    # RESOLUTION
    # --------------------------------------------------------

    resolution_delay = random.uniform(
        max(calculated_ist_hours + 1, 3),
        max(calculated_ist_hours + 3, calculated_ist_hours + 24)
    )

    resolved_at = (
        created_at
        + timedelta(hours=resolution_delay)
    )

    # --------------------------------------------------------
    # RMA / ESCALATION
    # --------------------------------------------------------

    rma_required = random.random() < 0.15

    if rma_required:
        rma_status = random.choice([
            "Requested",
            "Approved",
            "Shipped",
            "Delivered",
            "Customer Return Pending",
            "Shipment Delayed"
        ])
    else:
        rma_status = "Not Required"

    escalated = random.random() < 0.12

    # --------------------------------------------------------
    # SAVE RECORD
    # --------------------------------------------------------

    records.append({

        "incident_id": incident_id,

        "customer": customer,

        "segment": segment,

        "priority_initial": initial_priority,

        "priority_final": final_priority,

        "priority_changed": priority_changed,

        "priority_change_time": priority_change_time,

        "created_at": created_at,

        "first_response_at": first_response_at,

        "initial_solution_at": initial_solution_at,

        "resolved_at": resolved_at,

        "sla_target_hours": ist_sla_hours[final_priority],

        "reported_ist_hours": reported_ist_hours,

        "device_model": device,

        "location": location,

        "engineer": engineer,

        "shift": shift,

        "status": status,

        "customer_impact": customer_impact,

        "rma_required": rma_required,

        "rma_status": rma_status,

        "escalated": escalated,

        "description": description,

        # Evaluation-only ground truth.
        "synthetic_anomaly_type": anomaly_type
    })


# ============================================================
# DATAFRAME
# ============================================================

df = pd.DataFrame(records)


# ============================================================
# SAVE MAIN DATASET
# ============================================================

df.to_csv(
    "data/synthetic_incidents.csv",
    index=False
)

df.to_excel(
    "data/synthetic_incidents.xlsx",
    index=False
)


# ============================================================
# CREATE SEPARATE GROUND-TRUTH FILE
# ============================================================

ground_truth = df[
    [
        "incident_id",
        "synthetic_anomaly_type"
    ]
].copy()

ground_truth.to_csv(
    "data/evaluation_ground_truth.csv",
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

print()
print("=" * 70)
print("AI KPI / SLA ANOMALY INVESTIGATOR")
print("Synthetic Incident Dataset v3")
print("=" * 70)
print()

print(
    f"Total incidents generated: {len(df)}"
)

print()
print("Ground-truth anomaly distribution:")
print(
    df["synthetic_anomaly_type"]
    .value_counts()
)

print()
print("Priority distribution:")
print(
    df["priority_final"]
    .value_counts()
)

print()
print("Priority transition count:")
print(
    df["priority_changed"]
    .sum()
)

print()
print("Files created:")
print("data/synthetic_incidents.csv")
print("data/synthetic_incidents.xlsx")
print("data/evaluation_ground_truth.csv")

print()
print("=" * 70)
print("Dataset generation complete!")
print("=" * 70)
