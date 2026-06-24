# ============================================================
#  config.py — Cấu hình toàn bộ hệ thống
#  Sửa file này để thay đổi IP, ngưỡng, thông số camera
# ============================================================

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Kết nối ─────────────────────────────────────────────────
ESP32_IP   = "192.168.1.11"
ESP32_PORT = 80
ESP32_URL  = f"http://{ESP32_IP}:{ESP32_PORT}"

FIREBASE_URL = "https://project1-d5875-default-rtdb.firebaseio.com"

# ── Đường dẫn model ──────────────────────────────────────────
ANTISPOOF_MODEL = os.path.join(BASE_DIR, "models", "best_model_quantized.onnx")
LANDMARK_MODEL  = os.path.join(BASE_DIR, "models", "face_landmarker.task")
FACE_DB         = os.path.join(BASE_DIR, "models", "vectors.npz")

# ── Camera ───────────────────────────────────────────────────
CAMERA_ID    = 0
FRAME_WIDTH  = 640
FRAME_HEIGHT = 480

# ── AntiSpoof ────────────────────────────────────────────────
INPUT_SIZE    = 128
REAL_THRESHOLD = 0.80
SPOOF_MARGIN   = 0.15

# ── Nhận diện khuôn mặt ──────────────────────────────────────
CROP_SCALE           = 2.7
FACE_MATCH_THRESHOLD = 0.55
FACE_MIN_SIZE        = 100
FACE_MAX_SIZE        = 380
BLUR_THRESHOLD       = 35
FACE_CACHE_DURATION  = 3.0

# ── Blink detection ──────────────────────────────────────────
BLINK_CLOSE_THRESHOLD = 0.14
BLINK_OPEN_THRESHOLD  = 0.22
BLINK_MIN_DURATION    = 0.05
BLINK_MAX_DURATION    = 0.60

# ── Pose detection ───────────────────────────────────────────
POSE_LEFT_THRESHOLD  = 0.45
POSE_RIGHT_THRESHOLD = 2.20
POSE_HOLD_TIME       = 0.8

# ── Timeout ──────────────────────────────────────────────────
CHALLENGE_TIMEOUT  = 8.0
SESSION_TIMEOUT    = 25.0

# ── Cooldown gửi lệnh ────────────────────────────────────────
ESP32_RESEND_COOLDOWN = 5.0
SPOOF_ALERT_COOLDOWN  = 3.0

# ── Đăng ký khuôn mặt (3 góc) ────────────────────────────────
REGISTRATION_PHASES = [
    {"name": "NHIN THANG", "pose": "CENTER", "pitch": "NEUTRAL", "frames": 20},
    {"name": "QUAY TRAI",  "pose": "LEFT",   "pitch": "NEUTRAL", "frames": 20},
    {"name": "QUAY PHAI",  "pose": "RIGHT",  "pitch": "NEUTRAL", "frames": 20},
]
