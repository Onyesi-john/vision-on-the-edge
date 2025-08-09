docker exec -it vision-on-the-edge-app_green-1 sh -c "python3 - <<'EOF'
import cv2

def test_camera(index):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        print(f'/dev/video{index} ❌ Cannot open')
        return
    ret, frame = cap.read()
    if not ret or frame is None:
        print(f'/dev/video{index} ⚠️ Opened but no frames')
    else:
        print(f'/dev/video{index} ✅ Working, resolution = {frame.shape[1]}x{frame.shape[0]}')
    cap.release()

for i in range(0, 11):
    test_camera(i)
EOF"
