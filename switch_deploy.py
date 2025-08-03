#!/usr/bin/env python3
import subprocess
import os
import sys
import time

ACTIVE_FILE = "active_container.txt"
ENV_FILE = ".env"
DOCKER_NETWORK = "internal"

def run_cmd(cmd, check=True):
    print(f"📦 Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)

def get_active():
    if os.path.exists(ACTIVE_FILE):
        with open(ACTIVE_FILE) as f:
            val = f.read().strip()
            if val in ("blue", "green"):
                return val
    return "green"  # default fallback

def get_inactive(active):
    return "blue" if active == "green" else "green"

def update_env(active_color):
    print(f"📄 Updating {ENV_FILE} → ACTIVE_APP=app_{active_color}")
    with open(ENV_FILE, "w") as f:
        f.write(f"ACTIVE_APP=app_{active_color}\n")

def write_active(active_color):
    with open(ACTIVE_FILE, "w") as f:
        f.write(active_color)

def wait_for_healthy(service_name, timeout=60):
    """Wait until container is healthy (via docker inspect)."""
    print(f"⏳ Waiting for {service_name} to become healthy...")
    start = time.time()
    while time.time() - start < timeout:
        result = subprocess.run(
            f"docker inspect --format='{{{{.State.Health.Status}}}}' {service_name}",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and "healthy" in result.stdout:
            print(f"✅ {service_name} is healthy.")
            return True
        time.sleep(2)
    raise RuntimeError(f"Timeout waiting for {service_name} to become healthy")

def main():
    try:
        print("🔄 Starting Blue-Green switch...")

        active = get_active()
        inactive = get_inactive(active)

        print(f"🟢 Switching from {active} → {inactive}")

        # Start inactive app container
        run_cmd(f"docker compose up -d --no-deps --build app_{inactive}")

        # Wait for it to become healthy before routing traffic
        wait_for_healthy(f"vision-on-the-edge-app_{inactive}-1")

        # Update nginx routing environment
        update_env(inactive)

        # Restart nginx so it picks up the new env variable (force recreate)
        run_cmd("docker compose up -d --no-deps --build --force-recreate nginx")

        # Give nginx a short buffer to fully reload
        time.sleep(3)

        # Stop and remove the old app container
        run_cmd(f"docker compose stop app_{active}")
        run_cmd(f"docker compose rm -f app_{active}")

        # Write new active color
        write_active(inactive)

        print(f"✅ Switch complete: app_{inactive} is now live.")

    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e.cmd}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
