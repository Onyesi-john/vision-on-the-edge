import os
import csv
import matplotlib.pyplot as plt
import numpy as np

# Directory containing all ci_timing.log files
LOG_DIR = "ci_logs"
OUTPUT_CSV = "ci_stage_durations.csv"

# Collect all logs
log_files = [os.path.join(LOG_DIR, f) for f in os.listdir(LOG_DIR) if f.endswith(".log")]

all_runs = []

for log_file in log_files:
    run_name = os.path.splitext(os.path.basename(log_file))[0]
    timestamps = {}
    with open(log_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ts, stage = line.split(",", 1)
            timestamps[stage] = int(ts)

    # Compute stage durations aligned with workflow output
    stages = [
        ("checkout", "checkout_done", "buildx_setup_done"),
        ("docker_login", "buildx_setup_done", "docker_login_done"),
        ("docker_build", "docker_build_start", "docker_build_end"),
    ]
    durations = {}
    for name, start, end in stages:
        if start in timestamps and end in timestamps:
            durations[name] = timestamps[end] - timestamps[start]
        else:
            durations[name] = None
    durations["run_name"] = run_name
    all_runs.append(durations)

# Write CSV
with open(OUTPUT_CSV, "w", newline="") as csvfile:
    fieldnames = ["run_name", "checkout", "docker_login", "docker_build"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    for run in all_runs:
        writer.writerow(run)

print(f"CSV saved to {OUTPUT_CSV}")

# Optional: plot bar chart
run_names = [r["run_name"] for r in all_runs]
checkout_times = [r["checkout"] for r in all_runs]
login_times = [r["docker_login"] for r in all_runs]
build_times = [r["docker_build"] for r in all_runs]

x = np.arange(len(run_names))
width = 0.25

fig, ax = plt.subplots(figsize=(10,6))
ax.bar(x - width, checkout_times, width, label="Checkout")
ax.bar(x, login_times, width, label="Docker Login")
ax.bar(x + width, build_times, width, label="Docker Build")
ax.set_xticks(x)
ax.set_xticklabels(run_names, rotation=45, ha="right")
ax.set_ylabel("Duration (seconds)")
ax.set_title("CI/CD Stage Durations")
ax.legend()
plt.tight_layout()
plt.show()
