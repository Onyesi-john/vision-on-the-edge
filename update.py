import cv2

RTSP_URL = "rtsp://127.0.0.1:8554/live/stream"  # or your LAN IP, e.g., 192.168.x.x

cap = cv2.VideoCapture(RTSP_URL, cv2.CAP_FFMPEG)
if not cap.isOpened():
    print(f"Cannot open RTSP stream: {RTSP_URL}")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("Frame not received")
        break
    cv2.imshow("Stream", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
