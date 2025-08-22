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
START_DELAY = 10     # wait after starting new app before proceeding


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
    return "green"


def get_inactive(active):
    return "blue" if active == "green" else "green"


def write_active(active_color):
    with open(ACTIVE_FILE, "w") as f:
        f.write(active_color)


def wait_for_dns_resolution(upstream_name, timeout=30):
    """Wait until NGINX container can resolve the upstream hostname."""
    print(f"Waiting for {upstream_name} to be resolvable in {NGINX_CONTAINER_NAME}...")
    start = time.time()
    while time.time() - start < timeout:
        result = subprocess.run(
            f"docker exec {NGINX_CONTAINER_NAME} ping -c 1 -W 1 {upstream_name}",
            shell=True,
            capture_output=True
        )
        if result.returncode == 0:
            print(f"{upstream_name} is now resolvable.")
            return True
        time.sleep(1)
    raise RuntimeError(f"Timeout waiting for {upstream_name} to be resolvable in {NGINX_CONTAINER_NAME}")


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

    location /socket.io/ {{
        proxy_pass http://app_{target_color}:5000/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 3600s;
        proxy_buffering off;
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

        # Wait a bit for app initialization (camera etc.)
        print(f"Waiting {START_DELAY}s for app initialization...")
        time.sleep(START_DELAY)

        # Health checks and rollback are disabled for now

        # Update nginx config
        write_nginx_routing_config(inactive)

        # Ensure nginx is running
        run_cmd("docker compose up -d nginx")

        # Wait until upstream is resolvable from nginx container
        wait_for_dns_resolution(f"app_{inactive}")

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
