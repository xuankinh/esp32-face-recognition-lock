# ============================================================
#  core/recognition.py
#  AntiSpoof ONNX worker + InsightFace nhận diện
# ============================================================

import threading
import time
import numpy as np
import cv2
import onnxruntime as ort
from insightface.app import FaceAnalysis

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class AntiSpoofWorker:
    """Chạy ONNX inference trong thread riêng, không block camera."""

    def __init__(self):
        print("[INFO] Nạp model AntiSpoof ONNX...")
        sess_opt = ort.SessionOptions()
        sess_opt.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        sess_opt.intra_op_num_threads = 4
        providers = (
            ['CUDAExecutionProvider']
            if 'CUDAExecutionProvider' in ort.get_available_providers()
            else ['CPUExecutionProvider']
        )
        session = ort.InferenceSession(
            config.ANTISPOOF_MODEL, sess_options=sess_opt, providers=providers
        )
        self._session    = session
        self._input_name = session.get_inputs()[0].name

        self._lock   = threading.Lock()
        self._input  = None
        self._result = (False, 0.0)
        self._ready  = False
        self.infer_time_ms = 0.0

        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while True:
            face = None
            with self._lock:
                if self._input is not None:
                    face    = self._input.copy()
                    self._input = None
            if face is not None:
                try:
                    t0  = time.time()
                    img = cv2.resize(face, (config.INPUT_SIZE, config.INPUT_SIZE)).astype(np.float32)
                    img = np.expand_dims(np.transpose((img - 127.5) / 128.0, (2, 0, 1)), axis=0)
                    preds = self._session.run(None, {self._input_name: img})[0][0]
                    exp   = np.exp(preds - preds.max())
                    scores = exp / exp.sum()
                    real  = float(scores[1])
                    spoof = float(scores[0])
                    is_real = (
                        real > config.REAL_THRESHOLD
                        and (real - spoof) > config.SPOOF_MARGIN
                    )
                    self.infer_time_ms = (time.time() - t0) * 1000
                    with self._lock:
                        self._result = (is_real, real * 100)
                        self._ready  = True
                except Exception as e:
                    print(f"[SPOOF] Lỗi inference: {e}")
            time.sleep(0.01)

    def submit(self, face: np.ndarray):
        with self._lock:
            self._input = face.copy()

    def get_result(self):
        """Trả về ((is_real, conf_pct), is_ready)."""
        with self._lock:
            return self._result, self._ready

    def reset(self):
        with self._lock:
            self._ready  = False
            self._result = (False, 0.0)


class FaceRecognizer:
    """InsightFace embedding + so khớp cosine với DB."""

    def __init__(self):
        print(" Nạp InsightFace (buffalo_s)...")
        self.face_app = FaceAnalysis(name='buffalo_s')
        self.face_app.prepare(ctx_id=-1, det_size=(160, 160))

        self.db_vectors: list = []
        self.db_names:   list = []
        self._cache_name  = "UNKNOWN"
        self._cache_conf  = 0.0
        self._cache_time  = 0.0
        self.infer_time_ms = 0.0

        self._load_db()

    def _load_db(self):
        if os.path.exists(config.FACE_DB):
            data = np.load(config.FACE_DB)
            self.db_vectors = list(data["vectors"])
            self.db_names   = list(data["names"])
            print(f" Đã nạp {len(self.db_names)} người từ DB.")
        else:
            print("[WARN] Chưa có Face DB.")

    def reload_db(self):
        """Gọi sau khi đăng ký/xóa để load lại DB."""
        self._load_db()
        self._cache_time = 0.0  # Xóa cache

    def recognize(self, face: np.ndarray):
        """
        Nhận diện khuôn mặt.
        Có cache 3 giây để tránh gọi InsightFace liên tục.
        Trả về (name, score_percent).
        """
        now = time.time()
        if now - self._cache_time < config.FACE_CACHE_DURATION:
            return self._cache_name, self._cache_conf

        try:
            t0    = time.time()
            faces = self.face_app.get(face)
            self.infer_time_ms = (time.time() - t0) * 1000

            if not faces or not self.db_vectors:
                return "UNKNOWN", 0.0

            emb       = faces[0].embedding
            best_name = "UNKNOWN"
            best_sim  = -1.0

            for db_vec, db_name in zip(self.db_vectors, self.db_names):
                sim = float(
                    np.dot(emb, db_vec)
                    / (np.linalg.norm(emb) * np.linalg.norm(db_vec) + 1e-6)
                )
                if sim > best_sim:
                    best_sim, best_name = sim, db_name

            if best_sim > config.FACE_MATCH_THRESHOLD:
                self._cache_name = best_name
                self._cache_conf = best_sim * 100
            else:
                self._cache_name = "UNKNOWN"
                self._cache_conf = 0.0

            self._cache_time = now
            return self._cache_name, self._cache_conf

        except Exception as e:
            print(f"[RECOGNIZE] Lỗi: {e}")
            return "ERROR", 0.0

    def clear_cache(self):
        self._cache_time = 0.0
        self._cache_name = "UNKNOWN"
        self._cache_conf = 0.0
