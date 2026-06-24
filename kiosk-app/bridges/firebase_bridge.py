# ============================================================
#  bridges/firebase_bridge.py
#  Poll lệnh từ Web Admin + Ghi log DailyLogs
# ============================================================

import queue
import threading
import time
import requests
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class FirebaseBridge:
    def __init__(self):
        self._last_trigger  = 0
        self._last_status   = ""
        self._log_queue     = queue.Queue(maxsize=50)

        # Callbacks — gán từ bên ngoài
        self.on_register_face = None   # fn(name: str)
        self.on_delete_face   = None   # fn(name: str)
        self.on_door_status   = None   # fn(status: str)

        threading.Thread(target=self._poll_loop,  daemon=True).start()
        threading.Thread(target=self._log_worker, daemon=True).start()

    # ── Poll Firebase mỗi 0.5s ───────────────────────────────
    def _poll_loop(self):
        print("[FIREBASE] Lắng nghe lệnh từ Web Admin...")
        while True:
            try:
                r = requests.get(
                    f"{config.FIREBASE_URL}/RobotLeTan.json", timeout=3
                )
                if r.status_code == 200:
                    data = r.json()
                    if data and isinstance(data, dict):
                        # Xử lý lệnh Control
                        ctrl = data.get("Control", {})
                        if isinstance(ctrl, dict):
                            trigger = ctrl.get("trigger", 0)
                            if trigger != self._last_trigger:
                                self._last_trigger = trigger
                                self._handle_command(ctrl)
                        # Theo dõi trạng thái cửa từ ESP32
                        status = data.get("Status", "")
                        if status != self._last_status:
                            self._last_status = status
                            if self.on_door_status:
                                self.on_door_status(status)
            except Exception:
                pass
            time.sleep(0.5)

    def _handle_command(self, data: dict):
        cmd = data.get("command", "")
        if cmd == "REGISTER_NEW_FACE" and self.on_register_face:
            self.on_register_face(data.get("name", "Nguoi dung"))
        elif cmd == "DELETE_CARD" and self.on_delete_face:
            self.on_delete_face(data.get("name", ""))

    # ── Ghi log background ───────────────────────────────────
    def _log_worker(self):
        while True:
            path, payload = self._log_queue.get()
            try:
                requests.post(
                    f"{config.FIREBASE_URL}{path}.json",
                    json=payload, timeout=3
                )
            except Exception:
                pass

    def _push_log(self, path: str, data: dict):
        try:
            self._log_queue.put_nowait((path, data))
        except queue.Full:
            pass

    # ── Public API ───────────────────────────────────────────
    def log_face_recognized(self, name: str, score: float):
        today    = datetime.now().strftime("%d-%m-%Y")
        time_str = datetime.now().strftime("%H:%M:%S")
        self._push_log(f"/DailyLogs/{today}", {
            "type": "FACE", "name": name,
            "score": round(score, 1), "time": time_str, "cardId": "FACE_ID"
        })
        self._push_log("/RobotLeTan/AIEvents", {
            "command": "FACE_RECOGNIZED", "name": name
        })

    def log_register_success(self, name: str):
        self._push_log("/RobotLeTan/AIEvents", {
            "command": "FACE_REGISTER_SUCCESS", "name": name
        })
