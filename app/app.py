import threading
import time
import queue
import os
import cv2
import torch
from flask import Flask, render_template, Response
from ultralytics import YOLO

# Limit PyTorch threads to CPU cores
num_cores = os.cpu_count() or 1
torch.set_num_threads(num_cores)
torch.set_num_interop_threads(num_cores)

app = Flask(__name__)

# Check if app is active (used in blue-green deployment)
IS_ACTIVE = os.getenv("ACTIVE", "false").lower() == "true"

# Load YOLOv8 model on CPU
MODEL_PATH = "best.pt"
model = YOLO(MODEL_PATH)
model.to("cpu")

# Confidence & NMS thresholds
model.conf = 0.5
model.iou  = 0.45

SELECTED_CLASSES = ["person", "chair", "computer"]
DETECTED_CLASSES = [model.names.index(c) for c in SELECTED_CLASSES if c in model.names] if SELECTED_CLASSES else []

if IS_ACTIVE:
    print("[INFO] Starting camera since ACTIVE=true")
    
    # Camera setup
    camera = cv2.VideoCapture(0, cv2.CAP_ANY)
    if not camera.isOpened():
        raise RuntimeError("Could not open camera.")
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # Queues and threading
    frame_queue = queue.Queue(maxsize=1)
    result_frame = None
    lock = threading.Lock()

    def capture_thread():
        while True:
            ret, frame = camera.read()
            if not ret:
                continue
            if frame_queue.full():
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
            frame_queue.put(frame)

    def infer_thread():
        global result_frame
        while True:
            frame = frame_queue.get()
            small = cv2.resize(frame, (640, 360))
            results = model(small)[0]
            x_scale = frame.shape[1] / 640
            y_scale = frame.shape[0] / 360

            for box in results.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                if DETECTED_CLASSES and cls_id not in DETECTED_CLASSES:
                    continue
                if conf < model.conf:
                    continue

                x1, y1, x2, y2 = box.xyxy[0]
                x1, y1 = int(x1 * x_scale), int(y1 * y_scale)
                x2, y2 = int(x2 * x_scale), int(y2 * y_scale)

                label = f"{model.names[cls_id]} {conf:.2f}"
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            with lock:
                result_frame = frame.copy()

    threading.Thread(target=capture_thread, daemon=True).start()
    threading.Thread(target=infer_thread, daemon=True).start()

    last_time = time.time()
    frame_count = 0
    fps = 0

    def generate_frames():
        global last_time, frame_count, fps
        while True:
            if result_frame is None:
                continue
            with lock:
                out = result_frame.copy()

            frame_count += 1
            if time.time() - last_time >= 1.0:
                fps = frame_count
                frame_count = 0
                last_time = time.time()

            cv2.putText(out, f"FPS: {fps}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            _, buffer = cv2.imencode('.jpg', out)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

else:
    print("[INFO] Running in INACTIVE mode (no camera, no inference)")
    def generate_frames():
        while True:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health')
def health():
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
