# ============================================================
#  bridges/esp32_bridge.py
#  Gửi lệnh HTTP POST thẳng xuống ESP32
# ============================================================

import queue
import threading
import time
import requests

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class ESP32Bridge:
    def __init__(self, base_url: str = config.ESP32_URL):
        self.base_url   = base_url
        self.online     = False
        self.latency_ms = 0.0
        self._queue     = queue.Queue(maxsize=20)
        self._session   = requests.Session()
        self._last_cmd_time = 0.0

        threading.Thread(target=self._ping_loop,   daemon=True).start()
        threading.Thread(target=self._send_worker, daemon=True).start()

    # ── Ping kiểm tra ESP32 còn sống không ──────────────────
    def _ping_loop(self):
        while True:
            try:
                t = time.time()
                r = self._session.get(f"{self.base_url}/", timeout=1.5)
                if r.status_code in [200, 404]:
                    self.online     = True
                    self.latency_ms = (time.time() - t) * 1000
                else:
                    self.online = False
            except Exception:
                self.online     = False
                self.latency_ms = 0.0
            time.sleep(2)

    # ── Worker gửi lệnh từ queue ─────────────────────────────
    def _send_worker(self):
        while True:
            payload = self._queue.get()
            try:
                self._session.post(
                    f"{self.base_url}/api/control",
                    json=payload,
                    timeout=2.0
                )
            except Exception as e:
                print(f"[ESP32] Lỗi gửi: {e}")

    def _enqueue(self, payload: dict):
        """
        Chống flood: các lệnh thường cách nhau ít nhất 0.8s.
        Các lệnh quan trọng (FACE_RECOGNIZED, SPOOF, UNKNOWN)
        luôn được gửi ngay.
        """
        now = time.time()
        cmd = payload.get("command", "")
        important = {"FACE_RECOGNIZED", "SPOOF_ALERT", "FACE_UNKNOWN"}
        if cmd not in important:
            if now - self._last_cmd_time < 0.8:
                return
        self._last_cmd_time = now
        payload["trigger"] = now
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            print("[ESP32] Queue đầy, bỏ lệnh!")

    # ── Public API ───────────────────────────────────────────
    def face_recognized(self, name: str, score: float):
        print(f"[ESP32] → MỞ CỬA: {name} ({score:.1f}%)")
        self._enqueue({"command": "FACE_RECOGNIZED", "name": name, "targetID": 999})

    def face_unknown(self):
        print("[ESP32] → NGƯỜI LẠ")
        self._enqueue({"command": "FACE_UNKNOWN"})

    def spoof_alert(self, reason: str = ""):
        print(f"[ESP32] → GIẢ MẠO: {reason}")
        self._enqueue({"command": "SPOOF_ALERT", "reason": reason})

    def register_start(self, name: str):
        self._enqueue({"command": "START_REGISTER", "name": name})

    def register_done(self, name: str):
        self._enqueue({"command": "CHALLENGE_STEP", "step": "IDLE"})

    def challenge_step(self, step_name: str):
        self._enqueue({"command": "CHALLENGE_STEP", "step": step_name})
