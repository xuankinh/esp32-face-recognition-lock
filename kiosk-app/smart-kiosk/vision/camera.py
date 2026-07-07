# ============================================================
#  vision/camera.py
#  Đọc frame camera liên tục trong thread riêng
# ============================================================

import cv2
import threading
import time

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class CameraThread:
    def __init__(self,
                 cam_id: int = config.CAMERA_ID,
                 width:  int = config.FRAME_WIDTH,
                 height: int = config.FRAME_HEIGHT):
        self.cap = cv2.VideoCapture(cam_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

        self.frame     = None
        self.new_frame = False
        self.running   = True
        self._lock     = threading.Lock()

        threading.Thread(target=self._update, daemon=True).start()

    def _update(self):
        while self.running:
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self.frame     = frame
                    self.new_frame = True

    def read(self):
        """Trả về frame mới nhất, hoặc None nếu chưa có frame mới."""
        with self._lock:
            if self.new_frame and self.frame is not None:
                self.new_frame = False
                return self.frame.copy()
        return None

    def stop(self):
        self.running = False
        self.cap.release()
