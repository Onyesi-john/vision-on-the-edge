#!/usr/bin/env python3
import subprocess
import os
import sys
import time

ACTIVE_FILE = "active_container.txt"
NGINX_CONF_PATH = "./nginx/includes/active.conf"
NGINX_CONTAINER_NAME = "vision-on-the-edge-nginx-1"
DOCKER_NETWORK = "internal"

# Delays (seconds) to ensure smooth switching
STOP_DELAY = 5       # wait after stopping old app to release /dev/video0
START_DELAY = 3      # wait after starting new app before health check

def run_cmd(cmd, check=True):
    print(f"▶ Running: {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result

def get_active():
    if os.path.exists(ACTIVE_FILE):
        with open(ACTIVE_FILE) as f:
            val = f.read().strip()
            if val in ("blue", "green"):
                return val
    return "green"  # default fallback

def get_inactive(active):
    return "blue" if active == "green" else "green"

def write_active(active_color):
    with open(ACTIVE_FILE, "w") as f:
        f.write(active_color)

def wait_for_healthy(service_name, timeout=60):
    print(f"Waiting for {service_name} to become healthy...")
    start = time.time()
    while time.time() - start < timeout:
        result = subprocess.run(
            f"docker inspect --format='{{{{.State.Health.Status}}}}' {service_name}",
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and "healthy" in result.stdout:
            print(f"{service_name} is healthy.")
            return True
        time.sleep(2)
    raise RuntimeError(f"Timeout waiting for {service_name} to become healthy")

def write_nginx_routing_config(target_color):
    print(f"Writing new NGINX routing config → {NGINX_CONF_PATH}")
    with open(NGINX_CONF_PATH, "w") as f:
        f.write(f"""
server {{
    listen 8000;

    location / {{
        proxy_pass http://app_{target_color}:5000;
        proxy_connect_timeout 2s;
        proxy_read_timeout 3600s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }}

    location /video_feed {{
        proxy_pass http://app_{target_color}:5000/video_feed;

        proxy_http_version 1.1;
        proxy_set_header Connection '';

        proxy_buffering off;
        proxy_request_buffering off;
        proxy_cache off;
        sendfile off;
        tcp_nodelay on;
        chunked_transfer_encoding off;
        proxy_read_timeout 3600s;
    }}

    location /health {{
        proxy_pass http://app_{target_color}:5000/health;
        access_log off;
    }}
}}
""")

def test_nginx_config():
    print("Testing NGINX config...")
    result = subprocess.run(
        f"docker exec {NGINX_CONTAINER_NAME} nginx -t",
        shell=True,
        capture_output=True,
        text=True
    )
    print(result.stdout)
    print(result.stderr)
    return result.returncode == 0

def reload_nginx():
    print(f"Reloading NGINX config in container: {NGINX_CONTAINER_NAME}")
    if test_nginx_config():
        run_cmd(f"docker exec {NGINX_CONTAINER_NAME} nginx -s reload")
        print("NGINX reloaded successfully.")
    else:
        raise RuntimeError("NGINX config test failed; reload aborted.")

def main():
    try:
        print("Starting Blue-Green Deployment Switch")

        active = get_active()
        inactive = get_inactive(active)

        # Stop old app container
        run_cmd(f"docker compose stop app_{active}")
        run_cmd(f"docker compose rm -f app_{active}")

        # Wait to ensure device is released
        print(f"Waiting {STOP_DELAY}s for device release...")
        time.sleep(STOP_DELAY)

        # Start new app container
        run_cmd(f"docker compose up -d --no-deps --build app_{inactive}")

        # Wait a bit before health check so app can init camera
        print(f"Waiting {START_DELAY}s for app initialization...")
        time.sleep(START_DELAY)

        # Wait for health check to pass
        wait_for_healthy(f"vision-on-the-edge-app_{inactive}-1")

        # Update nginx config
        write_nginx_routing_config(inactive)

        # Ensure nginx is running
        run_cmd("docker compose up -d nginx")

        # Small delay before reload
        time.sleep(3)

        # Reload nginx to apply config
        reload_nginx()

        # Mark new app as active
        write_active(inactive)

        print(f"Switch complete: app_{inactive} is now live.")

    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e.cmd}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
