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

log = logging.getLogger("presensi.api")

_state: dict = {}


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


app = FastAPI(title="Presensi API", version="1.0.0",
              description="Face-recognition attendance API (v1)", lifespan=lifespan)


def require_key(x_api_key: str | None = Header(default=None)):
    """Dependency auth: header X-API-Key (FastAPI memetakan x_api_key -> x-api-key)."""
    cfg = _state["cfg"]
    expected = os.environ.get("PRES_API_KEY") or cfg["api"]["api_key"]
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header wajib")
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="API key salah")


async def read_frames(files: list[UploadFile], max_images: int) -> list[np.ndarray]:
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


# ---------------------------------------------------------------- endpoints ---
@app.get("/health")
def health():
    pipe: VerifyPipeline = _state["pipe"]
    return {"status": "ok", "model_version": _state["cfg"]["project"]["model_version"],
            "registered_users": len(pipe.gallery)}


@app.post("/api/enroll", dependencies=[Depends(require_key)])
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


@app.post("/api/verify", dependencies=[Depends(require_key)])
async def verify(files: list[UploadFile] = File(...),
                 user_id: str | None = Form(None)):
    """Batch frame -> verdict (1:1 bila user_id dikirim, else 1:N)."""
    pipe: VerifyPipeline = _state["pipe"]
    cfg = _state["cfg"]
    frames = await read_frames(files, cfg["api"]["max_images"])
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
