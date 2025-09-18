import os
import csv
import numpy as np
import matplotlib.pyplot as plt

# Directory containing all runs for a tool
LOG_DIR = "ci_timing_runs"
OUTPUT_CSV = "ci_stage_durations_avg.csv"

# Collect all logs
log_files = [os.path.join(LOG_DIR, f) for f in os.listdir(LOG_DIR) if f.endswith(".log")]
all_stage_durations = []

for log_file in log_files:
    stages = []
    with open(log_file, "r") as f:
        for line in f:
            line = line.strip()
            if "," not in line:
                continue
            ts, stage = line.split(",", 1)
            stages.append((stage, int(ts)))

    # Compute durations between consecutive stages
    durations = {}
    for i in range(len(stages) - 1):
        name = f"{stages[i][0]} → {stages[i+1][0]}"
        durations[name] = stages[i+1][1] - stages[i][1]

    all_stage_durations.append(durations)

# Collect all unique stage transitions
all_stage_names = sorted({name for d in all_stage_durations for name in d})

# Compute averages
avg_durations = {}
for stage in all_stage_names:
    values = [d[stage] for d in all_stage_durations if stage in d]
    avg_durations[stage] = np.mean(values) if values else None

# Save CSV
with open(OUTPUT_CSV, "w", newline="") as csvfile:
    fieldnames = ["stage", "avg_duration"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for stage, avg in avg_durations.items():
        writer.writerow({"stage": stage, "avg_duration": avg})

print(f"CSV saved to {OUTPUT_CSV}")

# Plot bar chart
stages = list(avg_durations.keys())
durations = [avg_durations[s] for s in stages]

fig, ax = plt.subplots(figsize=(10,6))
ax.bar(stages, durations)
ax.set_ylabel("Average Duration (seconds)")
ax.set_title("Average CI/CD Stage Durations")
ax.set_xticklabels(stages, rotation=45, ha="right")
plt.tight_layout()
plt.show()
