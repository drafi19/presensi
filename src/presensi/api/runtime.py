"""Shared runtime state + helpers (dipakai app.py & liveness_api.py — tanpa circular import)."""

from __future__ import annotations

import os

import cv2
import numpy as np
from fastapi import Header, HTTPException, UploadFile

_state: dict = {}


def require_key(x_api_key: str | None = Header(default=None)):
    """Auth dependency: header X-API-Key (dipakai semua endpoint /api/*)."""
    cfg = _state["cfg"]
    expected = os.environ.get("PRES_API_KEY") or cfg["api"]["api_key"]
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header wajib")
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="API key salah")


async def read_frames(files: list[UploadFile], max_images: int) -> list:
    """File upload -> list ndarray BGR. Validasi jumlah & dekode JPEG/PNG."""
    if not (1 <= len(files) <= max_images):
        raise HTTPException(status_code=422,
                            detail=f"jumlah frame harus 1..{max_images}")
    frames = []
    for f in files:
        data = await f.read()
        img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise HTTPException(status_code=422,
                                detail=f"file '{f.filename}' bukan JPEG/PNG valid")
        frames.append(img)
    return frames
