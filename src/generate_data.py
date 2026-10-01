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
# SLA TARGETS
# ============================================================

sla_hours = {
    "P1": 4,
    "P2": 8,
    "P3": 24,
    "P4": 48
}


# ============================================================
# STORAGE
# ============================================================

records = []


base_date = datetime(2026, 8, 1)


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
    # PRIORITY
    # --------------------------------------------------------

    initial_priority = random.choices(
        priorities,
        weights=[0.05, 0.15, 0.45, 0.35]
    )[0]

    final_priority = initial_priority

    priority_changed = False

    priority_change_time = None

    priority_transition_error = False


    # --------------------------------------------------------
    # CREATED TIME
    # --------------------------------------------------------

    created_at = base_date + timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )


    # ========================================================
    # PRIORITY TRANSITION
    # ========================================================

    if (
        initial_priority in ["P3", "P4"]
        and random.random() < 0.15
    ):

        final_priority = random.choice(["P1", "P2"])

        priority_changed = True

        priority_change_time = (
            created_at
            + timedelta(
                hours=random.randint(1, 8),
                minutes=random.randint(0, 59)
            )
        )


    # --------------------------------------------------------
    # FIRST RESPONSE
    # --------------------------------------------------------

    response_delay = timedelta(
        minutes=random.randint(10, 180)
    )

    first_response_at = created_at + response_delay


    # --------------------------------------------------------
    # INITIAL SOLUTION
    # --------------------------------------------------------

    solution_delay = timedelta(
        hours=random.randint(1, 24),
        minutes=random.randint(0, 59)
    )

    initial_solution_at = created_at + solution_delay


    # --------------------------------------------------------
    # RESOLUTION
    # --------------------------------------------------------

    resolution_delay = timedelta(
        hours=random.randint(2, 48),
        minutes=random.randint(0, 59)
    )

    resolved_at = created_at + resolution_delay


    # ========================================================
    # GROUND-TRUTH ANOMALY
    # ========================================================

    anomaly_type = "Normal"


    # ========================================================
    # PRIORITY TRANSITION
    #
    # IMPORTANT:
    # Some transitions are correct.
    # Some transitions intentionally contain bad IST.
    # ========================================================

    if priority_changed:

        # 60% = correct calculation
        # 40% = incorrect calculation

        if random.random() < 0.40:

            priority_transition_error = True

            anomaly_type = "Priority Transition IST Error"

        else:

            priority_transition_error = False


    # ========================================================
    # CALCULATE SYSTEM-REPORTED IST
    # ========================================================

    if initial_solution_at is not None:

        if (
            priority_changed
            and priority_transition_error
        ):

            # WRONG:
            # System includes time before escalation.

            reported_ist_hours = round(
                (
                    initial_solution_at
                    - created_at
                ).total_seconds() / 3600,
                2
            )

        elif (
            priority_changed
            and not priority_transition_error
        ):

            # CORRECT:
            # Clock starts when priority becomes P1/P2.

            reported_ist_hours = round(
                (
                    initial_solution_at
                    - priority_change_time
                ).total_seconds() / 3600,
                2
            )

        else:

            reported_ist_hours = round(
                (
                    initial_solution_at
                    - created_at
                ).total_seconds() / 3600,
                2
            )

    else:

        reported_ist_hours = None


    # ========================================================
    # MISSING TIMESTAMP ANOMALY
    # ========================================================

    if random.random() < 0.04:

        anomaly_type = "Missing Timestamp"

        if random.random() < 0.5:

            first_response_at = None

        else:

            initial_solution_at = None

            reported_ist_hours = None


    # ========================================================
    # IMPOSSIBLE TIMELINE ANOMALY
    # ========================================================

    if random.random() < 0.03:

        anomaly_type = "Impossible Timeline"

        first_response_at = (
            created_at
            - timedelta(
                minutes=random.randint(5, 60)
            )
        )


    # ========================================================
    # UNKNOWN ANOMALY 1
    #
    # Very long resolution time
    # ========================================================

    if random.random() < 0.03:

        anomaly_type = "Unusually Long Resolution"

        resolved_at = (
            created_at
            + timedelta(
                hours=random.randint(100, 180)
            )
        )


    # ========================================================
    # UNKNOWN ANOMALY 2
    #
    # Very long first response
    # ========================================================

    if random.random() < 0.03:

        anomaly_type = "Unusually Long Response"

        first_response_at = (
            created_at
            + timedelta(
                hours=random.randint(8, 18)
            )
        )


    # ========================================================
    # RMA
    # ========================================================

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


    # ========================================================
    # ESCALATION
    # ========================================================

    escalated = random.random() < 0.12


    # ========================================================
    # SAVE RECORD
    # ========================================================

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

        "sla_target_hours": sla_hours[final_priority],

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

        # ----------------------------------------------------
        # Ground truth ONLY.
        #
        # The anomaly detector must NOT use this.
        # ----------------------------------------------------

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
#
# This will eventually NOT be used by the application.
# It is only for evaluating our detector.
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
print("=" * 65)

print("EnterpriseNet Services")
print("Synthetic Incident Dataset v2")

print("=" * 65)

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

print("Files created:")

print("data/synthetic_incidents.csv")
print("data/synthetic_incidents.xlsx")
print("data/evaluation_ground_truth.csv")

print()

print("=" * 65)

print("Dataset generation complete!")

print("=" * 65)