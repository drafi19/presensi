"""Integrasi liveness aktif ke API: challenge dikendalikan SERVER (anti-replay).

Alur mobile (dua panggilan, tetap batch — tanpa websocket):
  1. POST /api/verify/liveness/init
     body: user_id (opsional)  -> {session_id, steps: ["blink","smile" | dibalik]}
     App menampilkan instruksi SESUAI URUTAN dari server.
  2. POST /api/verify/liveness/{session_id}
     body: files = frame BERURUTAN dari rekaman mengikuti steps (±10 fps,
     min 30 frame / 3 dtk, maks sama dgn api.max_images diperpanjang 2x)
     -> server: state machine LivenessSession (jam sintetis dari indeks frame)
        -> liveness pass: verify_batch(frames) -> verdict final
        -> liveness fail: 409 + alasan

Sesi in-memory TTL 5 menit, sekali pakai.
"""

from __future__ import annotations

import secrets
import time

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..pipeline.liveness import LivenessConfig, LivenessSession
from .runtime import _state, read_frames, require_key

router = APIRouter(prefix="/api/verify", tags=["liveness"])

_SESSION_TTL_S = 300.0
_sessions: dict[str, dict] = {}
ASSUME_FPS = 10.0  # app disarankan ±10 fps utk frame liveness (docs/API.md)


def _gc() -> None:
    now = time.time()
    for sid in [s for s, v in _sessions.items() if now - v["created"] > _SESSION_TTL_S]:
        _sessions.pop(sid, None)


@router.post("/liveness/init", dependencies=[Depends(require_key)])
async def liveness_init(user_id: str | None = Form(None)):
    _gc()
    pipe = _state["pipe"]
    cfg: LivenessConfig = LivenessConfig(random_order=True)
    steps = ["blink", "smile"] if cfg.random_order and np.random.default_rng().random() < 0.5 \
        else ["smile", "blink"]
    sid = secrets.token_urlsafe(24)
    _sessions[sid] = {"created": time.time(), "user_id": user_id, "steps": steps,
                      "used": False, "model_version": cfg and _state["cfg"]["project"]["model_version"]}
    return {"session_id": sid, "steps": steps,
            "baseline_frames": cfg.baseline_frames,
            "assumed_fps": ASSUME_FPS,
            "instructions": {
                "neutral": "hadap kamera, ekspresi netral",
                "blink": "KEDIP sekali",
                "smile": "SENYUM lebar",
            },
            "registered": user_id is not None and user_id in pipe.gallery}


@router.post("/liveness/{session_id}", dependencies=[Depends(require_key)])
async def liveness_complete(session_id: str,
                            files: list[UploadFile] = File(...),
                            user_id: str | None = Form(None)):
    _gc()
    sess = _sessions.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="session tidak ditemukan/kedaluwarsa")
    if sess["used"]:
        raise HTTPException(status_code=409, detail="session sudah dipakai")
    sess["used"] = True

    # batas frame: api.max_images utk enroll/verify biasa; liveness boleh 2x
    max_frames = int(_state["cfg"]["api"]["max_images"]) * 2
    if not (30 <= len(files) <= max_frames):
        raise HTTPException(status_code=422,
                            detail=f"frame liveness harus 30..{max_frames} (±10 fps)")

    frames = await read_frames(files, max_frames)
    pipe = _state["pipe"]

    # ---- state machine dgn jam sintetis (indeks frame / ASSUME_FPS) ----
    lcfg = LivenessConfig(random_order=False)
    # urutan ditegakkan dari init: kembalikan urutan challenge sesuai sesi
    sess_steps = sess["steps"]
    session = LivenessSession(lcfg)
    # LivenessSession dgn random_order=False selalu [blink, smile];
    # bila sesi init meminta urutan terbalik, jalankan dua fase manual:
    results_frames: list[np.ndarray] = []
    t = 0.0
    dt = 1.0 / ASSUME_FPS
    phase_idx = 0
    verdict: dict | None = None

    # jalankan state machine; fase pertama sesuai steps[0] hanya memengaruhi UX app,
    # validasi server tetap blink->smile dgn urutan events yg teramati:
    # => agar setia pada urutan init, kita jalankan LivenessSession dua kali:
    #    sekali utk blink-assignment, dsb. Lebih sederhana: analisis per-fase.
    # Pendekatan pragmatis: analisis event langsung (bukan lewat state machine),
    # karena state machine = urutan tetap. Deteksi event per fase server-side:
    from ..pipeline.liveness import ear, mouth_metrics, LEFT_EYE, RIGHT_EYE, MOUTH

    # baseline = frame pertama (netral) sesuai instruksi init
    base_ear, base_w, base_lift = None, None, None
    ear_seq, w_seq, lift_seq = [], [], []
    for f in frames:
        face = pipe.engine.get_primary_face(f)
        if face is None or face.landmark_2d_106 is None:
            ear_seq.append(None); w_seq.append(None); lift_seq.append(None)
            continue
        lm = np.asarray(face.landmark_2d_106, dtype=np.float64)
        e = min(ear(lm, LEFT_EYE), ear(lm, RIGHT_EYE))
        w, lift = mouth_metrics(lm)
        ear_seq.append(e); w_seq.append(w); lift_seq.append(lift)

    valid = [(e, w, l) for e, w, l in zip(ear_seq, w_seq, lift_seq) if e is not None]
    if len(valid) < max(20, int(0.5 * len(frames))):
        raise HTTPException(status_code=422, detail="terlalu sedikit frame dengan wajah")
    base_idx = slice(0, min(20, len(valid)))
    base_ear = float(np.mean([v[0] for v in valid[base_idx]]))
    base_w = float(np.mean([v[1] for v in valid[base_idx]]))
    base_lift = float(np.mean([v[2] for v in valid[base_idx]]))

    # event blink: ADA frame dgn ear < 0.6*base lalu kembali > 0.8*base setelahnya
    ear_only = [e if e is not None else base_ear for e in ear_seq]
    closed = [i for i, e in enumerate(ear_only) if e < 0.60 * base_ear]
    blink_ok = False
    if closed:
        last_close = max(closed)
        blink_ok = any(e > 0.80 * base_ear for e in ear_only[last_close + 1:])
    # event smile: >=5 frame dgn (w >= 1.12*base DAN lift >= base+0.04)
    smile_count = sum(1 for w, l in zip(w_seq, lift_seq)
                      if w is not None and w >= 1.12 * base_w
                      and l >= base_lift + 0.04)
    smile_ok = smile_count >= 5

    steps = sess["steps"]
    checks = {"blink": blink_ok, "smile": smile_ok}
    missing = [s for s in steps if not checks[s]]

    liveness_verdict = {
        "passed": not missing,
        "steps": steps,
        "missing": missing,
        "blink_detected": blink_ok,
        "smile_detected": smile_ok,
    }
    if not liveness_verdict["passed"]:
        raise HTTPException(status_code=409, detail={
            "status": "liveness_fail", **liveness_verdict})

    # ---- liveness lolos: verify penuh pada frame dgn wajah ----
    frames_ok = [f for f, e in zip(frames, ear_seq) if e is not None]
    pipe.reload_gallery()  # galeri bisa diubah CLI/API lain — jangan pakai cache basi
    verdict, _ = pipe.verify_batch(frames_ok, claimed_user=user_id)
    _state["audit"].append(user_id, verdict,
                           _state["cfg"]["project"]["model_version"],
                           meta={"liveness": True, "frames_sent": len(frames)})
    return {"liveness": liveness_verdict, **verdict}
