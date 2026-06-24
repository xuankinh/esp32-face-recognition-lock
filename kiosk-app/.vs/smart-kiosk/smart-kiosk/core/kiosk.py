# ============================================================
#  core/kiosk.py
#  SmartKioskV5 — vòng lặp chính, orchestrator
# ============================================================

import cv2
import mediapipe as mp
import threading
import time
import random
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from vision.camera      import CameraThread
from vision.cv_utils    import (check_face_size, check_blur, crop_face,
                                calc_ear, check_head_pose, check_pitch,
                                detect_screen, smooth_box)
from core.recognition   import AntiSpoofWorker, FaceRecognizer
from core.registration  import RegistrationManager, delete_face
from bridges.esp32_bridge    import ESP32Bridge
from bridges.firebase_bridge import FirebaseBridge
from ui.overlay         import (draw_face_guide, draw_status_bar,
                                draw_steps, draw_progress_bar,
                                draw_kpi_dashboard, draw_fps)
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


class SmartKioskV5:
    def __init__(self):
        print("[INFO] KHỞI ĐỘNG SMART AIOT KIOSK V5")

        # ── MediaPipe ─────────────────────────────────────────
        print("[INFO] Nạp MediaPipe FaceLandmarker...")
        base_opt = python.BaseOptions(model_asset_path=config.LANDMARK_MODEL)
        opts = vision.FaceLandmarkerOptions(
            base_options=base_opt, num_faces=1,
            min_face_detection_confidence=0.6,
            min_face_presence_confidence=0.6
        )
        self.mp_detector = vision.FaceLandmarker.create_from_options(opts)

        # ── AI modules ────────────────────────────────────────
        self.spoof      = AntiSpoofWorker()
        self.recognizer = FaceRecognizer()
        self.reg        = RegistrationManager()

        # ── Bridges ───────────────────────────────────────────
        print(f"[INFO] ESP32 URL: {config.ESP32_URL}")
        self.esp32    = ESP32Bridge()
        self.firebase = FirebaseBridge()
        self.firebase.on_register_face = self._cmd_register
        self.firebase.on_delete_face   = self._cmd_delete
        self.firebase.on_door_status   = self._cmd_door_status

        # ── Session state ─────────────────────────────────────
        self._reset_session()
        self._last_step_sent    = ""
        self.prev_box           = None
        self.cached_landmarks   = None

        # ── UI state ──────────────────────────────────────────
        self.pause_until = 0.0
        self.ui_status   = ""
        self.ui_color    = (0, 255, 0)
        self.show_kpi    = True

        # ── Telemetry ─────────────────────────────────────────
        self.real_door_hold_time = 0.0
        self._door_open_tick     = 0.0

        # ── Cooldowns ─────────────────────────────────────────
        self.last_esp32_send_name = ""
        self.last_esp32_send_time = 0.0
        self.last_spoof_alert_time = 0.0

        print("[SUCCESS] HỆ THỐNG SẴN SÀNG")

    # ==========================================================
    #  COMMANDS TỪ FIREBASE (Web Admin)
    # ==========================================================
    def _cmd_register(self, name: str):
        self.reg.start(name)
        self._reset_session()
        self.esp32.register_start(name)
        self._set_pause(f"CHUAN BI QUET: {name}", (0, 255, 255), 2.0)

    def _cmd_delete(self, name: str):
        new_vecs, new_names = delete_face(
            name, self.recognizer.db_vectors, self.recognizer.db_names
        )
        self.recognizer.db_vectors = new_vecs
        self.recognizer.db_names   = new_names
        self.recognizer.clear_cache()

    def _cmd_door_status(self, status: str):
        if status == "DOOR_OPEN":
            self._door_open_tick = time.time()
            self._reset_session()
            self._set_pause("CUA DA MO - TAM DUNG QUET", (0, 255, 0), 10.0)
        elif status == "READY" and self._door_open_tick > 0:
            self.real_door_hold_time = time.time() - self._door_open_tick
            self._door_open_tick = 0.0

    # ==========================================================
    #  SESSION
    # ==========================================================
    def _reset_session(self):
        self.blink_state      = "OPEN"
        self.blink_count      = 0
        self.blink_required   = 1
        self.blink_close_time = None
        self.face_height_open = 0.0
        self.pose_challenge   = random.choice(["LEFT", "RIGHT"])
        self.pose_hold_start  = None
        self.step             = "WAIT_FACE"
        self.session_start    = time.time()
        self.step_start       = time.time()
        self.recognizer.clear_cache()
        self.spoof.reset()

    def _set_pause(self, msg: str, color: tuple, duration: float):
        self.ui_status   = msg
        self.ui_color    = color
        self.pause_until = time.time() + duration

    # ==========================================================
    #  BLINK & POSE helpers (stateful nên giữ ở đây)
    # ==========================================================
    def _update_blink(self, ear: float, face_h: float):
        if self.blink_state == "OPEN":
            self.face_height_open = face_h
            if ear < config.BLINK_CLOSE_THRESHOLD:
                self.blink_state      = "CLOSED"
                self.blink_close_time = time.time()
        elif self.blink_state == "CLOSED":
            if self.face_height_open > 0:
                if abs(face_h - self.face_height_open) / self.face_height_open > 0.06:
                    self.blink_state = "OPEN"
                    return False, True   # is_fold cheat
            if ear > config.BLINK_OPEN_THRESHOLD:
                dur = time.time() - (self.blink_close_time or time.time())
                if config.BLINK_MIN_DURATION <= dur <= config.BLINK_MAX_DURATION:
                    self.blink_state  = "OPEN"
                    self.blink_count += 1
                    self.blink_close_time = None
                    return True, False
                self.blink_state      = "OPEN"
                self.blink_close_time = None
        return False, False

    def _update_pose(self, pose: str) -> bool:
        if pose == self.pose_challenge:
            if self.pose_hold_start is None:
                self.pose_hold_start = time.time()
            elif time.time() - self.pose_hold_start >= config.POSE_HOLD_TIME:
                return True
        else:
            self.pose_hold_start = None
        return False

    # ==========================================================
    #  MAIN LOOP
    # ==========================================================
    def run(self):
        camera       = CameraThread()
        prev_time    = time.time()
        smoothed_fps = 0.0
        frame_count  = 0

        print("[RUN] Vòng lặp camera bắt đầu. Q = thoát, K = bật/tắt KPI")

        while True:
            frame = camera.read()
            if frame is None:
                continue

            frame_count += 1
            frame   = cv2.flip(frame, 1)
            display = frame.copy()
            h, w    = frame.shape[:2]
            now     = time.time()
            status, color = "KHONG CO MAT", (0, 0, 255)

            # Session timeout
            if now - self.session_start > config.SESSION_TIMEOUT:
                self._reset_session()

            # MediaPipe detect (mỗi frame — đã tối ưu bên dưới)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            res = self.mp_detector.detect(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            )
            self.cached_landmarks = res.face_landmarks[0] if res.face_landmarks else None

            # ── UI Pause ──────────────────────────────────────
            if now < self.pause_until:
                status, color = self.ui_status, self.ui_color
                if self.reg.active and self.reg.phase < len(self.reg.phases):
                    draw_progress_bar(display, h, self.reg.frames_done,
                                      self.reg.total, True)

            # ── Không có mặt ──────────────────────────────────
            elif not self.cached_landmarks:
                self.prev_box = None
                draw_face_guide(display, w, h, 0, False)

            # ── Có mặt ────────────────────────────────────────
            else:
                lm  = self.cached_landmarks
                x1r = int(min(l.x for l in lm) * w)
                y1r = int(min(l.y for l in lm) * h)
                x2r = int(max(l.x for l in lm) * w)
                y2r = int(max(l.y for l in lm) * h)

                self.prev_box = smooth_box(self.prev_box, (x1r, y1r, x2r, y2r))
                x1, y1, x2, y2 = self.prev_box

                face_size     = max(x2 - x1, y2 - y1)
                size_ok, hint = check_face_size(x1, y1, x2, y2)
                draw_face_guide(display, w, h, face_size, size_ok)
                cv2.rectangle(
                    display, (x1, y1), (x2, y2),
                    (0, 255, 0) if size_ok else (0, 200, 255), 2
                )

                raw_face = frame[max(0,y1):min(h,y2), max(0,x1):min(w,x2)]

                if raw_face.size == 0:
                    status, color = "KHONG CO MAT", (0, 0, 255)
                elif not size_ok:
                    status, color = hint, (0, 200, 255)
                    if self.step != "WAIT_FACE" and not self.reg.active:
                        self.step = "WAIT_FACE"
                elif self.reg.active:
                    status, color = self._loop_registration(
                        lm, raw_face, display, h
                    )
                else:
                    status, color = self._loop_recognition(
                        frame, lm, raw_face, x1, y1, x2, y2, w, h, frame_count, now
                    )

            # ── Đồng bộ step xuống ESP32 ──────────────────────
            if self.step != self._last_step_sent and not self.reg.active:
                self._last_step_sent = self.step
                step_map = {
                    "PASSIVE":   "PASSIVE",
                    "BLINK":     "BLINK",
                    "POSE":      f"TURN_{self.pose_challenge}",
                    "RECOGNIZE": "RECOGNIZE",
                    "WAIT_FACE": "IDLE",
                }
                if self.step in step_map:
                    self.esp32.challenge_step(step_map[self.step])

            # ── FPS ───────────────────────────────────────────
            instant_fps  = 1.0 / (now - prev_time + 1e-6)
            smoothed_fps = 0.9 * smoothed_fps + 0.1 * instant_fps
            prev_time    = now

            # ── Render UI ─────────────────────────────────────
            draw_status_bar(display, status, color, self.esp32.online)
            draw_steps(display, w, self.step, self.reg.active)
            draw_fps(display, w, h, smoothed_fps)
            if self.show_kpi:
                draw_kpi_dashboard(
                    display, w, h, smoothed_fps,
                    self.esp32.latency_ms,
                    self.recognizer.infer_time_ms,
                    self.spoof.infer_time_ms,
                    self.real_door_hold_time
                )

            cv2.imshow("SMART AIOT KIOSK V5", display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key in (ord('k'), ord('K')):
                self.show_kpi = not self.show_kpi

        camera.stop()
        cv2.destroyAllWindows()
        print("[RUN] Đã dừng.")

    # ==========================================================
    #  LUỒNG ĐĂNG KÝ
    # ==========================================================
    def _loop_registration(self, lm, raw_face, display, h):
        phase_cfg    = self.reg.current_phase
        current_pose = check_head_pose(lm)
        current_pitch = check_pitch(lm)
        pose_ok  = current_pose  == phase_cfg["pose"]
        pitch_ok = current_pitch == phase_cfg["pitch"]

        if pose_ok and pitch_ok:
            self.reg.try_capture(raw_face, self.recognizer.face_app)
            status = f"[{phase_cfg['name']}] {self.reg.count}/{phase_cfg['frames']}"
            color  = (0, 255, 0)
        else:
            hint = ""
            if not pose_ok:  hint += f"QUAY {phase_cfg['pose']} "
            if not pitch_ok: hint += "NGANG LEN" if phase_cfg["pitch"] == "UP" else "CUI XUONG"
            status, color = f"YEU CAU: {hint.strip()}", (0, 200, 255)

        draw_progress_bar(display, h, self.reg.frames_done,
                          self.reg.total, pose_ok and pitch_ok)

        if self.reg.count >= phase_cfg["frames"]:
            done = self.reg.advance_phase()
            if done:
                saved_name = self.reg.save()
                self.recognizer.reload_db()
                self.esp32.register_done(saved_name)
                self.firebase.log_register_success(saved_name)
                self._set_pause("HOAN TAT DANG KY!", (0, 255, 0), 2.0)
            else:
                next_name = self.reg.current_phase["name"]
                self._set_pause(f"XONG! TIEP THEO: {next_name}", (0, 255, 255), 1.5)

        return status, color

    # ==========================================================
    #  LUỒNG NHẬN DIỆN 4 BƯỚC
    # ==========================================================
    def _loop_recognition(self, frame, lm, raw_face, x1, y1, x2, y2, w, h, frame_count, now):
        if self.step == "WAIT_FACE":
            self.step       = "PASSIVE"
            self.step_start = now

        sharp, blur_val = check_blur(raw_face)
        if not sharp:
            return f"BLUR ({blur_val:.0f})", (0, 0, 255)

        # ── BƯỚC 1: PASSIVE (AntiSpoof) ───────────────────────
        if self.step == "PASSIVE":
            if frame_count % 5 == 0:
                self.spoof.submit(crop_face(frame, x1, y1, x2, y2))
            (is_real, conf), ready = self.spoof.get_result()

            if not ready:
                return "DANG KIEM TRA...", (200, 200, 0)
            if not is_real:
                if now - self.last_spoof_alert_time > config.SPOOF_ALERT_COOLDOWN:
                    self.esp32.spoof_alert("ANTISPOOF")
                    self.last_spoof_alert_time = now
                return f"SPOOF! ({conf:.0f}%)", (0, 0, 255)

            roi = frame[max(0,y1-60):min(h,y2+60), max(0,x1-60):min(w,x2+60)]
            if detect_screen(roi):
                return "SCREEN DETECTED", (0, 0, 255)

            self.step, self.step_start = "BLINK", now
            self._set_pause("CHUAN BI NHAY MAT", (255, 165, 0), 1.5)
            return "OK - NHAY MAT 1 LAN", (255, 165, 0)

        # ── BƯỚC 2: BLINK ─────────────────────────────────────
        elif self.step == "BLINK":
            if now - self.step_start > config.CHALLENGE_TIMEOUT:
                self._reset_session()
                return "TIMEOUT", (0, 0, 255)

            ear, face_h   = calc_ear(lm, w, h)
            done, is_fold = self._update_blink(ear, face_h)

            if is_fold:
                self._reset_session()
                return "PHAT HIEN GAP ANH!", (0, 0, 255)
            if self.blink_count >= self.blink_required:
                self.step, self.step_start = "POSE", now
                self._set_pause(f"CHUAN BI QUAY {self.pose_challenge}", (0, 255, 255), 1.5)
                return f"BLINK OK - QUAY {self.pose_challenge}", (0, 255, 255)
            return "NHAY MAT 1 LAN", (255, 165, 0)

        # ── BƯỚC 3: POSE ──────────────────────────────────────
        elif self.step == "POSE":
            if now - self.step_start > config.CHALLENGE_TIMEOUT:
                self._reset_session()
                return "TIMEOUT", (0, 0, 255)

            pose     = check_head_pose(lm)
            hold_pct = 0
            if self.pose_hold_start:
                hold_pct = min(
                    int((now - self.pose_hold_start) / config.POSE_HOLD_TIME * 100), 100
                )
            if self._update_pose(pose):
                self.step, self.step_start = "RECOGNIZE", now
                self._set_pause("DANG NHAN DIEN...", (0, 255, 0), 1.0)
                return "OK - NHIN THANG", (0, 255, 0)
            return f"QUAY {self.pose_challenge} ({hold_pct}%)", (255, 255, 0)

        # ── BƯỚC 4: NHẬN DIỆN ────────────────────────────────
        elif self.step == "RECOGNIZE":
            recog_crop  = crop_face(frame, x1, y1, x2, y2)
            name, score = self.recognizer.recognize(recog_crop)

            if name == "UNKNOWN":
                if now - self.last_esp32_send_time > config.ESP32_RESEND_COOLDOWN:
                    self.esp32.face_unknown()
                    self.last_esp32_send_time = now
                return "KHONG XAC DINH", (0, 165, 255)

            if name == "ERROR":
                return "LOI NHAN DIEN", (0, 0, 255)

            # Nhận diện thành công
            if (name != self.last_esp32_send_name
                    or now - self.last_esp32_send_time > config.ESP32_RESEND_COOLDOWN):
                self.esp32.face_recognized(name, score)
                self.firebase.log_face_recognized(name, score)
                self.last_esp32_send_name = name
                self.last_esp32_send_time = now
                self._set_pause(f"MO CUA: {name}", (0, 255, 0), 10.0)
                threading.Timer(10.0, self._reset_session).start()

            return f"{name}  {score:.1f}%", (0, 255, 0)

        return "...", (128, 128, 128)
