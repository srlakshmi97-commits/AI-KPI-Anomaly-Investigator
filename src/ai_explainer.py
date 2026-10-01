import pandas as pd
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

# File paths
input_file = "data/anomaly_results.xlsx"
output_file = "data/ai_explanations.xlsx"

# Load anomaly results
df = pd.read_excel(input_file)

# Keep only detected anomalies
anomalies = df[df["anomaly_detected"] == True].head(5).copy()

print(f"Generating AI explanations for {len(anomalies)} anomalies...\n")

results = []

for _, row in anomalies.iterrows():

    context = f"""
Incident ID: {row.get('incident_id')}
Customer: {row.get('customer')}
Priority: {row.get('priority')}
Original Priority: {row.get('original_priority')}
Initial Solution Time Reported: {row.get('initial_solution_time_hours')}
Calculated IST: {row.get('calculated_ist_hours')}
IST Difference: {row.get('ist_difference_hours')}
Data Quality Issue: {row.get('data_quality_issue')}
Business Rule Violation: {row.get('business_rule_violation')}
Operational Anomaly: {row.get('operational_anomaly')}
Anomaly Category: {row.get('anomaly_category')}
Anomaly Reason: {row.get('anomaly_reason')}
Response Time: {row.get('response_time_hours')}
Resolution Time: {row.get('resolution_time_hours')}
"""

    prompt = f"""
You are an operations analytics assistant.

Analyze the following incident anomaly using ONLY the information provided.

Do not invent missing facts, causes, systems, people, or actions.

Incident information:
{context}

Provide the explanation using exactly these four sections:

1. What happened
Briefly describe the incident and the anomaly.

2. Why it was flagged
Explain which business rule, KPI rule, data-quality rule, or operational threshold triggered the flag.

3. Business impact
Explain the potential operational or customer impact based only on the supplied information.

4. What should be investigated next
Provide practical investigation steps based only on the available information.

Keep the explanation concise, professional, and suitable for an operations manager or executive review.
"""

    try:
        response = client.responses.create(
            model="gpt-5.6-luna",
            input=prompt
        )

        explanation = response.output_text

    except Exception as e:
        explanation = f"AI explanation failed: {str(e)}"

    results.append({
        "incident_id": row.get("incident_id"),
        "anomaly_category": row.get("anomaly_category"),
        "anomaly_reason": row.get("anomaly_reason"),
        "ai_explanation": explanation
    })

    print("=" * 80)
    print(f"Incident: {row.get('incident_id')}")
    print(explanation)
    print()

# Save results
output_df = pd.DataFrame(results)
output_df.to_excel(output_file, index=False)

print("=" * 80)
print(f"AI explanations saved to: {output_file}")