"""Deteksi + alignment + embedding wajah via InsightFace (buffalo_l).

FaceAnalysis membungkus:
  - detektor SCRFD (det_10g.onnx)
  - alignment landmark 5 titik + ArcFace w600k_r50 (embedding 512-d)

Catatan runtime: provider CPU saja untuk v1 (portable); GPU opsional nanti.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

log = logging.getLogger(__name__)

# Konversi config.yaml -> parameter FaceAnalysis (whitelist + cast eksplisit)
_PARAM_CAST: dict[str, type] = {
    "det_size": int,
    "det_thresh": float,
    "det_maxbox": int,
    "det_scale": float,
}


def _analysis_kwargs(cfg: dict) -> dict[str, Any]:
    out: dict[str, Any] = {"providers": ["CPUExecutionProvider"]}
    for key, value in (cfg or {}).items():
        cast = _PARAM_CAST.get(key.lower())
        if cast is not None:
            out[key.lower()] = cast(value)
    return out


class FaceEngine:
    """Loader tunggal SCRFD + ArcFace. `get_face(img)` -> wajah utama / None."""

    def __init__(self, models_dir: Path, det_cfg: dict | None = None):
        # import di dalam agar error message insightface jelas saat pertama dipakai
        from insightface.app import FaceAnalysis

        self.models_dir = Path(models_dir)
        self.app = FaceAnalysis(
            name="buffalo_l",
            root=str(self.models_dir.parent),  # insightface mencari <root>/models/buffalo_l
            **_analysis_kwargs(det_cfg),
        )
        self.app.prepare(ctx_id=-1, det_size=(640, 640))  # ctx_id=-1 = CPU

    def detect(self, img_bgr: np.ndarray) -> list:
        """Semua wajah terdeteksi (list insightface Face, urut skor deteksi)."""
        return self.app.get(img_bgr)

    def get_primary_face(self, img_bgr: np.ndarray):
        """Wajah dengan box terbesar (asumsi: subjek terdekat) atau None."""
        faces = self.detect(img_bgr)
        if not faces:
            return None
        return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    @staticmethod
    def embedding(face) -> np.ndarray | None:
        """Embedding 512-d ternormalisasi L2, atau None bila tidak tersedia."""
        normed = getattr(face, "normed_embedding", None)
        if normed is not None:
            return np.asarray(normed, dtype=np.float32)
        emb = getattr(face, "embedding", None)
        if emb is None:
            return None
        v = np.asarray(emb, dtype=np.float32)
        n = np.linalg.norm(v)
        return v / n if n > 0 else None

    @staticmethod
    def aligned_crop(img_bgr: np.ndarray, face, size: int = 224) -> np.ndarray:
        """Crop wajah ter-align (untuk input anti-spoof), resize ke size x size."""
        # landmark 5 titik dari detektor dipakai untuk crop sederhana yang stabil
        kps = face.kps  # (5, 2)
        x0, y0 = kps.min(axis=0)
        x1, y1 = kps.max(axis=0)
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        side = max(x1 - x0, y1 - y0) * 2.4  # padding sekitar landmark
        half = side / 2.0
        h, w = img_bgr.shape[:2]
        xA, yA = int(max(0, cx - half)), int(max(0, cy - half))
        xB, yB = int(min(w, cx + half)), int(min(h, cy + half))
        crop = img_bgr[yA:yB, xA:xB]
        if crop.size == 0:
            return np.zeros((size, size, 3), dtype=np.uint8)
        return cv2.resize(crop, (size, size), interpolation=cv2.INTER_LINEAR)
