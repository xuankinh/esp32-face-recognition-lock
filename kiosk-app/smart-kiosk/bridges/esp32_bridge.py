import queue
import threading
import time
import requests

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class ESP32Bridge:
    def __init__(self):
        self.online      = False
        self.latency_ms  = 0.0
        self._queue      = queue.Queue(maxsize=20)
        self._session    = requests.Session()

        threading.Thread(target=self._ping_loop,   daemon=True).start()
        threading.Thread(target=self._send_worker, daemon=True).start()

    # ── Ping để check ESP32 còn sống không ──────────────────
    def _ping_loop(self):
        while True:
            try:
                t0 = time.time()
                r  = self._session.get(f"{config.ESP32_URL}/", timeout=1.5)
                self.latency_ms = (time.time() - t0) * 1000
                self.online = (r.status_code in [200, 404])
            except Exception:
                self.online = False
            time.sleep(3)

    # ── Worker gửi lệnh tuần tự từ queue ────────────────────
    def _send_worker(self):
        while True:
            payload = self._queue.get()
            try:
                self._session.post(
                    f"{config.ESP32_URL}/api/control",
                    json=payload,
                    timeout=2.0
                )
            except Exception as e:
                print(f"[ESP32] Lỗi gửi: {e}")

    def _enqueue(self, payload: dict):
        try:
            payload["trigger"] = time.time()
            self._queue.put_nowait(payload)
        except queue.Full:
            print("[ESP32] Queue đầy, bỏ lệnh!")

    # [MỚI] Xóa sạch queue — gọi khi RFID vừa lock để tránh
    # lệnh Python cũ chạy ra sau khi RFID xong
    def flush_queue(self):
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                count += 1
            except queue.Empty:
                break
        if count > 0:
            print(f"[ESP32] Flush queue: đã xóa {count} lệnh.")

    # ── Các lệnh gửi xuống ESP32 ─────────────────────────────
    def face_recognized(self, name: str, score: float):
        print(f"[ESP32] → FACE_RECOGNIZED: {name} ({score:.1f}%)")
        self._enqueue({
            "command":  "FACE_RECOGNIZED",
            "name":     name,
            "targetID": 999
        })

    def face_unknown(self):
        print("[ESP32] → FACE_UNKNOWN")
        self._enqueue({"command": "FACE_UNKNOWN"})

    def spoof_alert(self, reason: str = ""):
        print(f"[ESP32] → SPOOF_ALERT: {reason}")
        self._enqueue({
            "command": "SPOOF_ALERT",
            "reason":  reason
        })

    def register_start(self, name: str):
        print(f"[ESP32] → START_REGISTER: {name}")
        self._enqueue({
            "command": "START_REGISTER",
            "name":    name
        })

    def register_done(self, name: str):
        print(f"[ESP32] → REGISTER_DONE: {name}")
        self._enqueue({
            "command": "CHALLENGE_STEP",
            "step":    "IDLE"
        })

    def challenge_step(self, step_name: str):
        self._enqueue({
            "command": "CHALLENGE_STEP",
            "step":    step_name
        })