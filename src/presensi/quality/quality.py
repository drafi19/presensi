"""Gerbang kualitas frame: blur, brightness, ukuran wajah.

Dipanggil sebelum deteksi (blur/brightness — murah) dan setelah deteksi
(ukuran wajah — butuh bounding box). Frame yang gagal dibuang sebelum
stage berat (anti-spoof, embedding).
"""

from __future__ import annotations

import cv2
import numpy as np


def blur_variance(img_bgr: np.ndarray) -> float:
    """Variance of Laplacian — proxy keburaman. Rendah = blur."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def mean_brightness(img_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    return float(gray.mean())


def face_too_small(box_xywh: tuple[int, int, int, int], min_px: int) -> bool:
    """box = (x, y, w, h) dari detektor. Wajah terlalu kecil -> embedding tak reliabel."""
    _x, _y, w, h = box_xywh
    return min(w, h) < min_px


def check_frame(img_bgr: np.ndarray, cfg: dict) -> tuple[bool, str | None]:
    """Cek blur + brightness. Return (ok, reason). reason None jika ok."""
    if img_bgr is None or img_bgr.size == 0:
        return False, "empty_frame"

    blur = blur_variance(img_bgr)
    if blur < cfg["blur_min_variance"]:
        return False, f"blurry(var={blur:.1f})"

    bright = mean_brightness(img_bgr)
    if bright < cfg["brightness_min"]:
        return False, f"too_dark(mean={bright:.1f})"
    if bright > cfg["brightness_max"]:
        return False, f"too_bright(mean={bright:.1f})"

    return True, None
