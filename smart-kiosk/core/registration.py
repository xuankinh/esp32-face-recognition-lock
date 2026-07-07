# ============================================================
#  core/registration.py
#  Quản lý luồng đăng ký khuôn mặt 3 góc
# ============================================================

import numpy as np
import cv2
import os
from collections import defaultdict

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config


class RegistrationManager:
    """
    Quản lý toàn bộ trạng thái và logic đăng ký khuôn mặt.
    Tách biệt hoàn toàn khỏi vòng lặp camera chính.
    """

    def __init__(self):
        self.active   = False
        self.name     = ""
        self.vectors  = []          # list of (vec, phase_idx, quality)
        self.phase    = 0
        self.count    = 0
        self.phases   = []
        self.total    = 0
        self._skip    = 0           # frame skip counter

    def start(self, name: str):
        self.active  = True
        self.name    = name
        self.vectors = []
        self.phase   = 0
        self.count   = 0
        self._skip   = 0
        self.phases  = list(config.REGISTRATION_PHASES)
        self.total   = sum(p["frames"] for p in self.phases)
        print(f"[REGISTER] Bắt đầu: {name} — {self.total} frames / {len(self.phases)} góc")

    def reset(self):
        self.active = False
        self.name   = ""
        self.vectors = []

    @property
    def current_phase(self) -> dict:
        return self.phases[self.phase]

    @property
    def frames_done(self) -> int:
        return sum(self.phases[i]["frames"] for i in range(self.phase)) + self.count

    def try_capture(self, raw_face: np.ndarray, face_app) -> bool:
        """
        Thử lấy 1 frame embedding. Trả về True nếu lấy được.
        Gọi mỗi frame khi pose & pitch đúng.
        """
        self._skip += 1
        if self._skip % 2 != 0:    # lấy 1 frame / 2
            return False

        gray   = cv2.cvtColor(raw_face, cv2.COLOR_BGR2GRAY)
        blur   = cv2.Laplacian(gray, cv2.CV_64F).var()
        bright = np.mean(gray)
        if not (blur > 50 and 40 < bright < 220):
            return False

        try:
            faces = face_app.get(raw_face)
            if not faces:
                return False
            vec = faces[0].embedding
            vec = vec / (np.linalg.norm(vec) + 1e-6)
            quality = min(blur / 200.0, 1.0)
            self.vectors.append((vec, self.phase, quality))
            self.count += 1
            return True
        except Exception:
            return False

    def advance_phase(self) -> bool:
        """
        Chuyển sang phase tiếp theo.
        Trả về True nếu đã xong tất cả phase.
        """
        self.phase += 1
        self.count  = 0
        return self.phase >= len(self.phases)

    def save(self) -> str:
        """
        Lưu vectors vào DB. Trả về tên người vừa lưu.
        """
        if not self.vectors:
            print("[REGISTER] Không có vector nào!")
            return ""

        actual_name  = self.name
        phase_groups = defaultdict(list)
        for vec, phase_idx, quality in self.vectors:
            phase_groups[phase_idx].append((vec, quality))

        final_vectors, final_names = [], []
        for phase_idx, items in phase_groups.items():
            items.sort(key=lambda x: x[1], reverse=True)
            top  = items[:min(6, len(items))]
            half = max(1, len(top) // 2)
            for chunk in [top[:half], top[half:]]:
                if not chunk:
                    continue
                vecs     = [v for v, _ in chunk]
                mean_vec = np.mean(vecs, axis=0)
                mean_vec = mean_vec / (np.linalg.norm(mean_vec) + 1e-6)
                final_vectors.append(mean_vec)
                final_names.append(actual_name)

        # Merge với DB cũ, xóa bản cũ của người này
        if os.path.exists(config.FACE_DB):
            data      = np.load(config.FACE_DB)
            old_pairs = [
                (v, n) for v, n in zip(data["vectors"], data["names"])
                if n != actual_name
            ]
            old_vecs  = [p[0] for p in old_pairs]
            old_names = [p[1] for p in old_pairs]
        else:
            old_vecs, old_names = [], []

        all_vecs  = old_vecs  + final_vectors
        all_names = old_names + final_names
        np.savez(config.FACE_DB, vectors=all_vecs, names=all_names)

        print(f"[REGISTER] Đã lưu {len(final_vectors)} vectors cho '{actual_name}'")
        self.reset()
        return actual_name


def delete_face(name: str, db_vectors: list, db_names: list) -> tuple:
    """
    Xóa tất cả vectors của 'name' khỏi DB.
    Trả về (new_vectors, new_names).
    """
    if not name or name not in db_names:
        print(f"[DELETE] Không tìm thấy: {name}")
        return db_vectors, db_names

    new_vecs  = [v for v, n in zip(db_vectors, db_names) if n != name]
    new_names = [n for n in db_names if n != name]
    np.savez(config.FACE_DB, vectors=new_vecs, names=new_names)
    print(f"[DELETE] Đã xóa: {name}")
    return new_vecs, new_names
