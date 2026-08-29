"""Unit test liveness (geometri + state machine) — wajah sintetis, tanpa kamera."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presensi.pipeline.liveness import (  # noqa: E402
    LEFT_EYE, MOUTH, RIGHT_EYE, LivenessConfig, LivenessSession, ear,
    mouth_metrics)

CX, CY = 320.0, 240.0
EYE_W = 40.0


def make_face(ear_val: float, mouth_w: float, mouth_lift: float) -> np.ndarray:
    """Wajah 106-titik sintetis dgn EAR & geometri mulut terkontrol."""
    lm = np.zeros((106, 2))
    h = ear_val * EYE_W
    for ring, ex in ((LEFT_EYE, CX - 80), (RIGHT_EYE, CX + 80)):
        for k, i in enumerate(ring):
            lm[i, 0] = ex + (k % 5) * 10.0
            lm[i, 1] = (CY - 60) + (h / 2 if k < 5 else -h / 2)
    mx0 = CX - mouth_w / 2
    for k, i in enumerate(MOUTH):
        t = k / (len(MOUTH) - 1)
        lm[i, 0] = mx0 + t * mouth_w
        corner = k in (0, len(MOUTH) - 1)
        lm[i, 1] = (CY + 80) - (mouth_lift * mouth_w if corner else 0.0)
    for i in range(106):
        if lm[i, 0] == 0 and lm[i, 1] == 0:
            lm[i] = (CX + (i % 7 - 3) * 2, CY + (i % 5 - 2) * 2)
    return lm


NEUTRAL = dict(ear_val=0.25, mouth_w=100.0, mouth_lift=0.0)
CLOSED = dict(ear_val=0.10, mouth_w=100.0, mouth_lift=0.0)
SMILING = dict(ear_val=0.25, mouth_w=130.0, mouth_lift=0.08)


def feed(sess: LivenessSession, face_kwargs: dict | None, n: int, t0: float,
         dt: float = 0.1) -> dict:
    """n frame; None = wajah hilang. Return state terakhir."""
    st = {}
    for i in range(n):
        lm = make_face(**face_kwargs) if face_kwargs is not None else None
        st = sess.update(lm, t0 + i * dt)
    return st


# ------------------------------------------------------------- metrik dasar ---
def test_ear_metrik():
    lm = make_face(**NEUTRAL)
    assert ear(lm, LEFT_EYE) == pytest.approx(0.25, abs=1e-6)
    assert ear(lm, RIGHT_EYE) == pytest.approx(0.25, abs=1e-6)


def test_mouth_metrik():
    lm = make_face(**SMILING)
    w, lift = mouth_metrics(lm)
    assert w == pytest.approx(130.0, abs=1e-6)
    assert lift == pytest.approx(0.08, abs=1e-6)


# ------------------------------------------------------------ state machine ---
def test_baseline_selesai_lalu_challenge():
    sess = LivenessSession(LivenessConfig(random_order=False))
    st = feed(sess, NEUTRAL, 25, t0=0.0)
    assert st["phase"] == "blink"          # urutan tetap: blink dulu
    assert sess._base_ear == pytest.approx(0.25, abs=1e-3)


def test_kedip_dan_senyum_lengkap():
    sess = LivenessSession(LivenessConfig(random_order=False))
    feed(sess, NEUTRAL, 25, t0=0.0)                 # baseline 0.0-2.4s
    st = feed(sess, NEUTRAL, 3, t0=3.0)             # mata terbuka -> armed
    st = feed(sess, CLOSED, 3, t0=4.0)              # tertutup
    st = feed(sess, NEUTRAL, 3, t0=5.0)             # terbuka lagi -> blink OK
    assert st["phase"] == "smile"
    st = feed(sess, SMILING, 6, t0=6.0)             # senyum stabil
    assert st["done"] is True
    assert st["phase"] == "done"


def test_foto_statis_gagal_timeout():
    """Wajah statis (foto) lolos baseline tapi GAGAL saat challenge."""
    sess = LivenessSession(LivenessConfig(random_order=False))
    feed(sess, NEUTRAL, 25, t0=0.0)
    st = feed(sess, NEUTRAL, 85, t0=3.0, dt=0.1)    # diam terus >8 dtk
    assert st["failed"] is True
    assert "timeout" in st["reason"]


def test_wajah_hilang_tidak_langsung_gagal():
    sess = LivenessSession(LivenessConfig(random_order=False))
    feed(sess, NEUTRAL, 25, t0=0.0)
    st = feed(sess, None, 20, t0=3.0)               # keluar frame 2 dtk
    assert st["failed"] is False
    assert st["phase"] in ("blink", "smile")


def test_timeout_menghitung_wajah_hilang():
    sess = LivenessSession(LivenessConfig(random_order=False))
    feed(sess, NEUTRAL, 25, t0=0.0)
    st = feed(sess, None, 85, t0=3.0, dt=0.1)       # hilang >8 dtk
    assert st["failed"] is True


def test_smile_butuh_lebar_dan_lift():
    """Senyum setengah (lebar naik, lift tidak) TIDAK terhitung."""
    sess = LivenessSession(LivenessConfig(random_order=False))
    feed(sess, NEUTRAL, 25, t0=0.0)
    feed(sess, NEUTRAL, 3, t0=3.0)
    feed(sess, CLOSED, 3, t0=4.0)
    st = feed(sess, NEUTRAL, 3, t0=5.0)
    assert st["phase"] == "smile"
    half = dict(ear_val=0.25, mouth_w=130.0, mouth_lift=0.0)  # lebar saja
    st = feed(sess, half, 10, t0=6.0)
    assert st["phase"] == "smile" and st["done"] is False


def test_urutan_challenge_beragam():
    """random_order=True: kedua urutan muncul di banyak sesi (anti-replay)."""
    orders = set()
    for seed in range(50):
        np.random.seed(seed)
        sess = LivenessSession(LivenessConfig(random_order=True))
        st = feed(sess, NEUTRAL, 25, t0=0.0)
        orders.add(st["phase"])
    assert orders == {"blink", "smile"}


def test_progress_baseline():
    sess = LivenessSession(LivenessConfig(random_order=False))
    st = feed(sess, NEUTRAL, 10, t0=0.0)
    assert st["progress"] == pytest.approx(10 / 25)
