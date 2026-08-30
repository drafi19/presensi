"""FastAPI app — kontrak API v1 untuk mobile client (DESAIN.md §7).

Jalankan: uv run? tidak — `python -m uvicorn presensi.api.app:app` dari root
dengan venv aktif, atau `python scripts/run_api.py`.

Auth: header `X-API-Key` (config api.api_key, override via env PRES_API_KEY).
Endpoint /health terbuka (tanpa key) untuk monitoring sederhana.
"""

from __future__ import annotations

import io
import logging
import os
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile

from ..pipeline.verify import VerifyPipeline, load_config
from .audit import AuditLog
from .liveness_api import router as liveness_router
from .runtime import _state, read_frames, require_key

log = logging.getLogger("presensi.api")


def _err(status: int, description: str, detail) -> tuple:
    """Helper responses={...} utk error codes di OpenAPI."""
    return (status, {"description": description,
                     "content": {"application/json": {"examples": {
                         "error": {"value": {"detail": detail}}}}}})


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    pipe = VerifyPipeline(cfg)
    audit = AuditLog(cfg["paths"]["gallery_dir"])
    _state["pipe"] = pipe
    _state["audit"] = audit
    _state["cfg"] = cfg
    log.info("Pipeline siap: %d user terdaftar", len(pipe.gallery))
    yield
    audit.close()
    _state.clear()


app = FastAPI(title="Presensi API", version="1.1.0",
              description="Face-recognition attendance API (v1 + active liveness)",
              lifespan=lifespan)
app.include_router(liveness_router)


# ---------------------------------------------------------------- endpoints ---
_VERIFY_RESPONSES = {
    200: {
        "description": "Verdict (200 berarti sistem jalan; keputusan ada di field `status`)",
        "content": {"application/json": {"examples": {
            "match": {"summary": "match — wajah cocok (user_id non-null)",
                      "value": {"status": "match", "user_id": "raihan",
                                "confidence": 0.98, "frames_valid": 5, "frames_total": 5}},
            "no_match": {"summary": "no_match — wajah valid, bukan kandidat",
                         "value": {"status": "no_match", "user_id": None,
                                   "confidence": 0.15, "frames_valid": 5, "frames_total": 5}},
            "spoof": {"summary": "spoof — foto/layar terdeteksi",
                      "value": {"status": "spoof", "user_id": None,
                                "confidence": 0.17, "frames_valid": 5, "frames_total": 5}},
            "no_face": {"summary": "no_face — tak ada wajah di frame",
                        "value": {"status": "no_face", "user_id": None,
                                  "confidence": None, "frames_valid": 0, "frames_total": 5}},
            "low_quality": {"summary": "low_quality — buram/gelap/frame valid kurang",
                            "value": {"status": "low_quality", "user_id": None,
                                      "confidence": None, "frames_valid": 0, "frames_total": 5}},
        }}}},
    **dict([
        _err(401, "API key hilang", "X-API-Key header wajib"),
        _err(403, "API key salah", "API key salah"),
        _err(422, "Payload bermasalah", "file 'f001.jpg' bukan JPEG/PNG valid"),
    ]),
}


@app.get("/health")
def health():
    pipe: VerifyPipeline = _state["pipe"]
    return {"status": "ok", "model_version": _state["cfg"]["project"]["model_version"],
            "registered_users": len(pipe.gallery)}


@app.post("/api/enroll", dependencies=[Depends(require_key)], responses={
    200: {
        "description": "Enroll berhasil",
        "content": {"application/json": {"examples": {
            "ok": {"value": {"user_id": "raihan", "enrolled": True, "accepted": 5,
                             "min_required": 3, "rejected": [],
                             "model_version": "buffalo_l", "n_embeddings": 5}},
        }}}},
    **dict([
        _err(401, "API key hilang", "X-API-Key header wajib"),
        _err(403, "API key salah", "API key salah"),
        _err(422, "Lolos gate kurang dari minimal",
             {"user_id": "cici", "enrolled": False, "accepted": 1, "min_required": 3,
              "rejected": [{"index": 2, "reason": "blurry(var=36.0)"}],
              "model_version": "buffalo_l"}),
    ]),
})
async def enroll(user_id: str = Form(...),
                 files: list[UploadFile] = File(...)):
    """Enroll/replace user: N gambar -> embeddings tersimpan (DESAIN §5)."""
    pipe: VerifyPipeline = _state["pipe"]
    cfg = _state["cfg"]
    frames = await read_frames(files, cfg["api"]["max_images"])
    summary = pipe.enroll_user(user_id, frames)
    if not summary["enrolled"]:
        raise HTTPException(status_code=422, detail=summary)
    return summary


@app.post("/api/verify", dependencies=[Depends(require_key)],
          responses=_VERIFY_RESPONSES)
async def verify(files: list[UploadFile] = File(...),
                 user_id: str | None = Form(None)):
    """Batch frame -> verdict (1:1 bila user_id dikirim, else 1:N)."""
    pipe: VerifyPipeline = _state["pipe"]
    cfg = _state["cfg"]
    frames = await read_frames(files, cfg["api"]["max_images"])
    pipe.reload_gallery()  # galeri bisa diubah CLI/API lain — jangan pakai cache basi
    verdict, _per_frame = pipe.verify_batch(frames, claimed_user=user_id)
    _state["audit"].append(user_id, verdict,
                           cfg["project"]["model_version"],
                           meta={"frames_sent": len(frames)})
    return verdict


@app.get("/api/enroll/{user_id}", dependencies=[Depends(require_key)])
def get_user(user_id: str):
    info = _state["pipe"].user_info(user_id)
    if info is None:
        raise HTTPException(status_code=404, detail="user tidak terdaftar")
    return info


@app.delete("/api/enroll/{user_id}", dependencies=[Depends(require_key)])
def delete_user(user_id: str):
    ok = _state["pipe"].remove_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="user tidak terdaftar")
    return {"deleted": user_id}


@app.get("/api/audit/recent", dependencies=[Depends(require_key)])
def audit_recent(limit: int = 50):
    return _state["audit"].recent(limit=min(limit, 500))
