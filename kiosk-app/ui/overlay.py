# ============================================================
#  ui/overlay.py
#  Tất cả hàm vẽ UI lên frame OpenCV
# ============================================================

import cv2
import numpy as np

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


def draw_face_guide(display, w: int, h: int, face_size: int, ok: bool):
    """Vẽ oval hướng dẫn + thanh mức kích thước."""
    color = (0, 255, 0) if ok else (0, 200, 255)
    cv2.ellipse(display, (w // 2, h // 2), (160, 210), 0, 0, 360, color, 2)

    bx, by, bw, bh = w - 30, 80, 16, h - 160
    cv2.rectangle(display, (bx, by), (bx + bw, by + bh), (60, 60, 60), -1)

    if config.FACE_MAX_SIZE > config.FACE_MIN_SIZE and face_size > 0:
        ratio  = min(max(
            (face_size - config.FACE_MIN_SIZE) /
            (config.FACE_MAX_SIZE - config.FACE_MIN_SIZE), 0.0), 1.0
        )
        fill_h = int(bh * ratio)
        cv2.rectangle(
            display,
            (bx, by + bh - fill_h), (bx + bw, by + bh),
            color, -1
        )


def draw_status_bar(display, status: str, color: tuple, esp32_online: bool):
    """Vẽ thanh trạng thái góc trên trái."""
    esp_color = (0, 255, 0) if esp32_online else (0, 0, 255)
    cv2.rectangle(display, (5, 5), (220, 42), (0, 0, 0), -1)
    cv2.putText(
        display,
        f"ESP32: {'OK' if esp32_online else 'OFFLINE'}",
        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, esp_color, 2
    )
    cv2.putText(
        display, status,
        (20, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.85, color, 2
    )


def draw_steps(display, w: int, current_step: str, registration_mode: bool):
    """Vẽ danh sách bước xác thực góc trên phải."""
    if registration_mode:
        cv2.putText(
            display, "[ DANG KY 5 GOC ]",
            (w - 220, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1
        )
        return
    steps = ["PASSIVE", "BLINK", "POSE", "RECOGNIZE"]
    for i, s in enumerate(steps):
        color = (0, 255, 0) if s == current_step else (80, 80, 80)
        cv2.putText(
            display, f"[{i+1}] {s}",
            (w - 160, 30 + i * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
        )


def draw_progress_bar(display, h: int, done: int, total: int, ok: bool):
    """Vẽ thanh tiến trình đăng ký góc dưới trái."""
    color = (0, 255, 0) if ok else (0, 200, 255)
    if total > 0:
        fill = int(done / total * 300)
        cv2.rectangle(display, (20, h - 40), (20 + fill, h - 20), color, -1)


def draw_kpi_dashboard(display, w: int, h: int,
                       fps: float, latency_ms: float,
                       face_infer_ms: float, spoof_infer_ms: float,
                       door_hold_time: float):
    """Vẽ bảng KPI góc dưới phải (bật/tắt bằng phím K)."""
    door_str = f"{door_hold_time:.2f} s" if door_hold_time > 0 else "Waiting..."
    kpis = [
        "--- REAL-TIME TELEMETRY ---",
        f"Pipeline FPS : {int(fps)}",
        f"LAN Ping     : {int(latency_ms)} ms",
        f"Face Infer   : {int(face_infer_ms)} ms",
        f"Spoof Eval   : {int(spoof_infer_ms)} ms",
        f"Servo Hold   : {door_str}",
    ]
    box_w, box_h = 250, 150
    overlay = display.copy()
    cv2.rectangle(overlay, (w - box_w, h - box_h), (w - 10, h - 10), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.6, display, 0.4, 0, display)

    for i, text in enumerate(kpis):
        c = (0, 255, 255) if i == 0 else (0, 255, 0)
        cv2.putText(
            display, text,
            (w - box_w + 10, h - box_h + 25 + i * 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.45, c, 1
        )


def draw_fps(display, w: int, h: int, fps: float):
    cv2.putText(
        display, f"FPS {int(fps)}",
        (w - 90, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1
    )
