#!/usr/bin/env python3

import subprocess
import os
import sys
from pathlib import Path

# Constants
BLUE = "blue"
GREEN = "green"
ACTIVE_CONTAINER_FILE = "active_container.txt"
DOCKER_NETWORK = "internal"
ENV_FILE = ".env"

def run_cmd(cmd, check=True):
    """Run shell command and print it."""
    print(f"📦 Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)

def ensure_docker_network_exists(network_name):
    """Ensure the internal Docker network is created."""
    result = subprocess.run(
        f"docker network ls --format '{{{{.Name}}}}' | grep -w {network_name}",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    if result.returncode != 0:
        print(f"🔧 Creating Docker network: {network_name}")
        run_cmd(f"docker network create {network_name}")

def get_active():
    """Return current active deployment (blue or green), or None."""
    if os.path.exists(ACTIVE_CONTAINER_FILE):
        with open(ACTIVE_CONTAINER_FILE) as f:
            return f.read().strip()
    return None

def get_inactive(active):
    """Return the inactive deployment based on current active."""
    if active == BLUE:
        return GREEN
    return BLUE

def update_env_file(active_app_name):
    """Write .env file for Docker Compose to pick up new active app."""
    print(f"📄 Updating {ENV_FILE} to ACTIVE_APP={active_app_name}")
    with open(ENV_FILE, "w") as f:
        f.write(f"ACTIVE_APP={active_app_name}\n")

def write_active_file(name):
    """Write the name of the active container to file."""
    with open(ACTIVE_CONTAINER_FILE, "w") as f:
        f.write(name)

def docker_compose_up(service_name):
    """Start specified service with docker-compose."""
    run_cmd(f"docker compose up -d {service_name}")

def docker_compose_stop(service_name):
    """Stop specified service with docker-compose."""
    run_cmd(f"docker compose stop {service_name}")

def build_and_restart_nginx():
    """Rebuild and restart nginx to point to new backend."""
    run_cmd("docker compose up -d --build nginx")

def main():
    try:
        print("🔄 Starting Blue-Green switch...")

        # Ensure network exists
        ensure_docker_network_exists(DOCKER_NETWORK)

        # Determine current and next deployments
        active = get_active()
        inactive = get_inactive(active) if active else BLUE  # Start BLUE if first time

        print(f"🟢 Switching to: {inactive}")
        if not active:
            print("🆕 No active container found. Bootstrapping deployment.")

        # Start the inactive app
        docker_compose_up(f"app_{inactive}")

        # Update nginx environment and restart
        update_env_file(f"app_{inactive}")
        build_and_restart_nginx()

        # Stop the old active container if switching
        if active:
            docker_compose_stop(f"app_{active}")

        # Update active record
        write_active_file(inactive)

        print(f"✅ App_{inactive} is now live via NGINX.")
        sys.exit(0)

    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e.cmd}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
