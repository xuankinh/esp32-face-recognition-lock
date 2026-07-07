# ============================================================
#  vision/cv_utils.py
#  Các hàm Computer Vision thuần túy (không state)
# ============================================================

import cv2
import numpy as np

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def check_face_size(x1, y1, x2, y2):
    """Kiểm tra khuôn mặt có nằm trong khoảng kích thước cho phép không."""
    size = max(x2 - x1, y2 - y1)
    if size < config.FACE_MIN_SIZE:
        return False, f"LAI GAN HOM ({size}px)"
    if size > config.FACE_MAX_SIZE:
        return False, f"LUI RA HOM ({size}px)"
    return True, ""


def check_blur(face: np.ndarray):
    """Trả về (is_sharp, blur_score)."""
    gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
    val  = cv2.Laplacian(gray, cv2.CV_64F).var()
    return val > config.BLUR_THRESHOLD, val


def crop_face(frame: np.ndarray, x1, y1, x2, y2):
    """Crop vùng mặt rộng hơn bounding box (dùng CROP_SCALE)."""
    h, w  = frame.shape[:2]
    cx    = (x1 + x2) / 2
    cy    = (y1 + y2) / 2
    side  = max(x2 - x1, y2 - y1) * config.CROP_SCALE / 2
    return frame[
        int(max(0, cy - side)):int(min(h, cy + side)),
        int(max(0, cx - side)):int(min(w, cx + side))
    ]


def calc_ear(lm, w: int, h: int):
    """
    Tính Eye Aspect Ratio (EAR) và chiều cao khuôn mặt.
    Trả về (ear, face_height).
    """
    def pt(i): return np.array([lm[i].x * w, lm[i].y * h])

    def _ear(idx):
        p = [pt(i) for i in idx]
        return (
            np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])
        ) / (2.0 * np.linalg.norm(p[0] - p[3]))

    ear = (_ear([33, 160, 158, 133, 153, 144]) +
           _ear([362, 385, 387, 263, 373, 380])) / 2
    face_height = np.linalg.norm(pt(10) - pt(152))
    return ear, face_height


def check_head_pose(lm) -> str:
    """Trả về 'LEFT' | 'RIGHT' | 'CENTER'."""
    nose  = lm[1]
    ratio = abs(nose.x - lm[234].x) / (abs(lm[454].x - nose.x) + 1e-6)
    if ratio < config.POSE_LEFT_THRESHOLD:  return "LEFT"
    if ratio > config.POSE_RIGHT_THRESHOLD: return "RIGHT"
    return "CENTER"


def check_pitch(lm) -> str:
    """Trả về 'UP' | 'DOWN' | 'NEUTRAL'."""
    ratio = abs(lm[152].y - lm[1].y) / (abs(lm[1].y - lm[10].y) + 1e-6)
    if ratio < 0.85: return "UP"
    if ratio > 1.35: return "DOWN"
    return "NEUTRAL"


def detect_screen(roi: np.ndarray) -> bool:
    """Phát hiện màn hình (hình chữ nhật lớn) trong ROI."""
    if roi.size == 0:
        return False
    gray  = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 80, 150)
    contours, _ = cv2.findContours(
        edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    for c in contours:
        if cv2.contourArea(c) > 15000:
            approx = cv2.approxPolyDP(c, 0.02 * cv2.arcLength(c, True), True)
            if len(approx) == 4:
                return True
    return False


def smooth_box(prev_box, new_box, alpha: float = 0.7):
    """Làm mượt bounding box giữa 2 frame."""
    if prev_box is None:
        return new_box
    x1r, y1r, x2r, y2r = new_box
    return (
        int(alpha * prev_box[0] + (1 - alpha) * x1r),
        int(alpha * prev_box[1] + (1 - alpha) * y1r),
        int(alpha * prev_box[2] + (1 - alpha) * x2r),
        int(alpha * prev_box[3] + (1 - alpha) * y2r),
    )
