#!/bin/bash
set -e

IMAGE_NAME="oyinc/edge_deployment:latest"
SWITCH_SCRIPT="/home/john/vision-on-the-edge/switch_deploy.py"
ENV_FILE="/home/john/vision-on-the-edge/.env"

# Quick internet check
if ! ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
    echo "[WARN] No internet connection, skipping update check."
    exit 0
fi

echo "[INFO] Pulling latest image..."
if ! docker pull "$IMAGE_NAME"; then
    echo "[ERROR] Failed to pull image. Skipping update."
    exit 1
fi

# Get digest of latest pulled image
NEW_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "$IMAGE_NAME" 2>/dev/null || echo "")

# Get digest of currently running active container
ACTIVE_CONTAINER=$(docker ps --filter "name=app_" --format "{{.ID}}" | head -n 1)
OLD_DIGEST=""
if [ -n "$ACTIVE_CONTAINER" ]; then
    OLD_IMAGE=$(docker inspect --format='{{.Config.Image}}' "$ACTIVE_CONTAINER")
    OLD_DIGEST=$(docker inspect --format='{{index .RepoDigests 0}}' "$OLD_IMAGE" 2>/dev/null || echo "")
fi

if [ "$NEW_DIGEST" != "$OLD_DIGEST" ]; then
    echo "[INFO] New image found. Updating deployment..."

    # Update IMAGE_NAME in .env so switch script uses it
    sed -i "s|^IMAGE_NAME=.*|IMAGE_NAME=$IMAGE_NAME|" "$ENV_FILE"

    # Switch to new version
    python3 "$SWITCH_SCRIPT"
else
    echo "[INFO] No update available."
fi
