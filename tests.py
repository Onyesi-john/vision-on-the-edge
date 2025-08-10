import os
import subprocess
import cv2

def get_camera_info(dev):
    """Try to get camera name using v4l2-ctl."""
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--device", dev, "--all"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Card type" in line:
                    return line.strip()
    except FileNotFoundError:
        pass
    return "Unknown camera"

def test_camera(dev):
    """Try to open camera and grab one frame."""
    try:
        cap = cv2.VideoCapture(dev)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            return ret
    except:
        pass
    return False

def list_cameras():
    print("📷 Scanning connected cameras...\n")
    devices = sorted([d for d in os.listdir("/dev") if d.startswith("video")])
    for dev in devices:
        path = f"/dev/{dev}"
        info = get_camera_info(path)
        status = "✅ Working" if test_camera(path) else "❌ Not working"
        print(f"{path:<12} → {info:<40} [{status}]")

if __name__ == "__main__":
    list_cameras()
