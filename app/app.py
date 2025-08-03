import threading
import time
import queue
import os
import cv2
import torch
import numpy as np
from flask import Flask, render_template, Response, jsonify
from ultralytics import YOLO
from pathlib import Path
import uuid

app = Flask(__name__)

# ------------------------------
# Settings
# ------------------------------
IS_ACTIVE = os.getenv("ACTIVE", "false").lower() == "true"
VIDEO_DEVICE = os.getenv("VIDEO_DEVICE", "0")
STREAM_FPS = int(os.getenv("STREAM_FPS", "5"))
MODEL_PATH = str(Path(__file__).parent / "best.pt")
SELECTED_CLASSES = ["person", "chair", "computer"]

# ------------------------------
# Globals
# ------------------------------
INSTANCE_ID = str(uuid.uuid4())  # Unique per container instance
is_ready = False
model = None
camera = None
frame_queue = queue.Queue(maxsize=1)
annotated_frame = None
raw_frame = None
lock = threading.Lock()

# Torch thread limits
num_cores = os.cpu_count() or 1
torch.set_num_threads(num_cores)
torch.set_num_interop_threads(num_cores)

# ------------------------------
# Capture Thread
# ------------------------------
def capture_thread():
    global raw_frame
    while True:
        ret, frame = camera.read()
        if not ret:
            continue
        raw_frame = frame.copy()

        if frame_queue.full():
            try:
                frame_queue.get_nowait()
            except queue.Empty:
                pass
        frame_queue.put(frame)

# ------------------------------
# Inference Thread
# ------------------------------
def infer_thread():
    global annotated_frame, model
    detected_ids = [
        model.names.index(c) for c in SELECTED_CLASSES if c in model.names
    ] if SELECTED_CLASSES else []

    while True:
        try:
            frame = frame_queue.get(timeout=1)
        except queue.Empty:
            continue

        small = cv2.resize(frame, (640, 360))
        results = model(small)[0]

        x_scale = frame.shape[1] / 640
        y_scale = frame.shape[0] / 360

        for box in results.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            if detected_ids and cls_id not in detected_ids:
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
            annotated_frame = frame.copy()

# ------------------------------
# Background Initializer
# ------------------------------
def init_inference():
    global is_ready, model, camera
    print("[INFO] Loading YOLO model...")
    model = YOLO(MODEL_PATH)
    model.to("cpu")
    model.conf = 0.5
    model.iou = 0.45

    print(f"[INFO] Opening camera: {VIDEO_DEVICE}")
    cam_index = int(VIDEO_DEVICE) if VIDEO_DEVICE.isdigit() else VIDEO_DEVICE
    camera = cv2.VideoCapture(cam_index, cv2.CAP_ANY)
    if not camera.isOpened():
        raise RuntimeError(f"Could not open camera {VIDEO_DEVICE}.")
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    threading.Thread(target=capture_thread, daemon=True).start()
    threading.Thread(target=infer_thread, daemon=True).start()

    is_ready = True
    print("[INFO] Inference started.")

if IS_ACTIVE:
    threading.Thread(target=init_inference, daemon=True).start()

# ------------------------------
# Streaming Generator
# ------------------------------
def generate_frames():
    last_time = time.time()
    frame_count = 0
    fps = 0
    min_frame_interval = 1.0 / STREAM_FPS

    while True:
        if not is_ready or raw_frame is None:
            placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(placeholder, "Initializing Camera...", (120, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            _, buffer = cv2.imencode('.jpg', placeholder)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(0.05)
            continue

        now = time.time()
        if now - last_time < min_frame_interval:
            time.sleep(0.001)
            continue

        with lock:
            display_frame = annotated_frame if annotated_frame is not None else raw_frame.copy()

        frame_count += 1
        if now - last_time >= 1.0:
            fps = frame_count
            frame_count = 0
            last_time = now

        cv2.putText(display_frame, f"FPS: {fps}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        _, buffer = cv2.imencode('.jpg', display_frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# ------------------------------
# Flask Routes
# ------------------------------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health')
def health():
    return ("OK", 200) if is_ready else ("LOADING", 503)

@app.route('/version')
def version():
    return jsonify({
        "active": os.getenv("ACTIVE", "false"),
        "instance_id": INSTANCE_ID
    })

if __name__ == '__main__':
    print("[INFO] Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
