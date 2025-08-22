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
from collections import deque
import uuid
import logging
from flask_socketio import SocketIO, emit
from datetime import datetime
import atexit
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Flask + SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
ASYNC_MODE = os.getenv("ASYNC_MODE", "threading")
socketio = SocketIO(app, async_mode=ASYNC_MODE, cors_allowed_origins="*")

# Settings from .env
IS_ACTIVE = os.getenv("ACTIVE", "true").lower() == "true"
VIDEO_DEVICE = os.getenv("VIDEO_DEVICE", "/dev/video0")  # string path
STREAM_FPS = int(os.getenv("STREAM_FPS", "5"))
MODEL_PATH = os.getenv("MODEL_PATH", str(Path(__file__).parent / "best.pt"))
DEPLOYMENT_COLOR = os.getenv("DEPLOYMENT_COLOR", "blue").lower()
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
LOG_HISTORY_SIZE = 100

# Parse selected classes from .env
selected = os.getenv("SELECTED_CLASSES", "")  # e.g., "person,chair,car"
SELECTED_CLASSES = [s.strip() for s in selected.split(",") if s.strip()]

# Globals
INSTANCE_ID = str(uuid.uuid4())
is_ready = False
model = None
camera = None
frame_queue = queue.Queue(maxsize=1)
annotated_frame = None
raw_frame = None
lock = threading.Lock()
stop_threads = threading.Event()
stats = {"fps": 0, "processing_time": 0, "object_count": 0, "detected_objects": {}}
log_history = deque(maxlen=LOG_HISTORY_SIZE)

# Torch optimization
torch.set_num_threads(os.cpu_count() or 1)

def add_log_entry(message, log_type="info", data=None):
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "type": log_type,
        "message": message,
        "data": data
    }
    log_history.append(entry)
    try:
        socketio.emit('log', entry)
    except Exception:
        pass

# Capture frames from camera
def capture_thread():
    global raw_frame, camera, stats
    frame_count = 0
    start_time = time.time()

    while not stop_threads.is_set():
        if camera is None or not camera.isOpened():
            time.sleep(0.5)
            continue

        ret, frame = camera.read()
        if not ret:
            time.sleep(0.1)
            continue

        raw_frame = frame
        frame_count += 1

        # Calculate FPS
        if time.time() - start_time >= 2:
            with lock:
                stats["fps"] = frame_count / 2
            frame_count = 0
            start_time = time.time()

        if frame_queue.full():
            frame_queue.get_nowait()
        frame_queue.put(frame)

# Inference and annotation
def infer_thread():
    global annotated_frame, model, stats
    add_log_entry("Inference thread started")

    allowed_ids = None if not SELECTED_CLASSES else [
    cls_id for cls_id, cls_name in model.names.items() if cls_name in SELECTED_CLASSES
]


    while not stop_threads.is_set():
        try:
            frame = frame_queue.get(timeout=1)
        except queue.Empty:
            continue

        t0 = time.time()
        results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False,
                        classes=allowed_ids if allowed_ids else None)
        proc_time = (time.time() - t0) * 1000

        current_objects = {}
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                label = model.names[cls_id]
                current_objects[label] = current_objects.get(label, 0) + 1

        annotated = results[0].plot() if len(results) > 0 else frame

        with lock:
            annotated_frame = annotated
            stats["processing_time"] = proc_time
            stats["object_count"] = sum(current_objects.values())
            stats["detected_objects"] = current_objects

        # Always log inference, even if nothing detected
        add_log_entry(f"Inference done. Objects: {current_objects}", "debug")

        try:
            socketio.emit('stats', stats)
        except Exception:
            pass


# Initialize camera and model
def init_inference():
    global is_ready, model, camera
    add_log_entry(f"Loading YOLO model from {MODEL_PATH}")
    try:
        model = YOLO(MODEL_PATH)
        model(np.zeros((240, 320, 3), dtype=np.uint8))  # warmup
    except Exception as e:
        add_log_entry(f"Model load error: {e}", "error")
        return

    camera = cv2.VideoCapture(VIDEO_DEVICE)
    if not camera.isOpened():
        add_log_entry(f"Camera {VIDEO_DEVICE} failed to open", "error")
        camera = None
        return

    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    threading.Thread(target=capture_thread, daemon=True).start()
    threading.Thread(target=infer_thread, daemon=True).start()
    is_ready = True
    add_log_entry("Inference ready", "info")

def cleanup():
    stop_threads.set()
    time.sleep(0.5)
    if camera and camera.isOpened():
        camera.release()
    add_log_entry("Cleanup complete", "info")

atexit.register(cleanup)

# Streaming generator
# Streaming generator
def generate_frames():
    min_interval = 1.0 / STREAM_FPS
    placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(placeholder, "Initializing...", (150, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    while not stop_threads.is_set():
        start_time = time.time()

        # Always choose a safe frame
        with lock:
            if annotated_frame is not None:
                frame = annotated_frame.copy()
            elif raw_frame is not None:
                frame = raw_frame.copy()
            else:
                frame = placeholder.copy()

        # Overlay FPS if stats available
        fps_text = f"FPS: {stats.get('fps', 0):.1f}"
        cv2.putText(frame, fps_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Encode to JPEG safely
        ret, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ret or jpeg is None:
            logger.warning("JPEG encoding failed, skipping frame")
            continue

        buf = jpeg.tobytes()
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buf + b"\r\n")

        # Frame pacing
        elapsed = time.time() - start_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)

app.config['TEMPLATES_AUTO_RELOAD'] = True
app_version = datetime.now().timestamp()

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response
# Flask routes
@app.route('/')
def home():
    return render_template('index.html', 
                         active=IS_ACTIVE, 
                         classes=SELECTED_CLASSES, 
                         DEPLOYMENT_COLOR=DEPLOYMENT_COLOR,
                         CONFIDENCE_THRESHOLD=CONFIDENCE_THRESHOLD,
                         timestamp=datetime.now().timestamp())

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

#@app.route('/health')
#def health():
    """
    Returns 200 only when inference is ready, otherwise 503.
    """
#    if is_ready:
#        return jsonify({"status": "ready", "instance_id": INSTANCE_ID}), 200
#    else:
#        return jsonify({"status": "loading", "instance_id": INSTANCE_ID}), 503


# SocketIO
@socketio.on('connect')
def handle_connect(_):
    emit('status', {'message': 'Connected', 'ready': is_ready})
    emit('log_history', list(log_history))
    if is_ready:
        emit('stats', stats)

@socketio.on('request_deployment_status')
def handle_deployment_status(_):
    emit('deployment_status', {"active": DEPLOYMENT_COLOR})

@app.route("/deployment_status")
def deployment_status():
    return jsonify({"active": DEPLOYMENT_COLOR})


# Main
if __name__ == "__main__":
    if IS_ACTIVE:
        threading.Thread(target=init_inference, daemon=True).start()
    socketio.run(app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
