"""Unit test matcher: cosine, match_score, vote_frame_results (tanpa model)."""

from __future__ import annotations

import numpy as np
import pytest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presensi.pipeline.matcher import cosine, match_1to1, match_score, vote_frame_results  # noqa: E402


def vec(seed: int) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=512).astype(np.float32)
    return v / np.linalg.norm(v)


# ---------------------------------------------------------------- cosine ----
def test_cosine_identik():
    v = vec(1)
    assert cosine(v, v) == pytest.approx(1.0, abs=1e-6)


def test_cosine_beda_jauh():
    a, b = vec(2), vec(3)
    assert abs(cosine(a, b)) < 0.3  # vektor acak ~0


# ------------------------------------------------------------ match_score ---
def test_match_score_pilih_terbaik():
    gallery = {"budi": vec(10), "ani": vec(11)}
    q = vec(10)  # identik budi
    user, sim, second = match_score(q, gallery)
    assert user == "budi"
    assert sim == pytest.approx(1.0, abs=1e-6)
    assert second < sim


def test_match_score_gallery_kosong():
    user, sim, _ = match_score(vec(1), {})
    assert user is None and sim == -1.0


def test_match_1to1():
    a, b = vec(5), vec(6)
    assert match_1to1(a, a) == pytest.approx(1.0, abs=1e-6)
    assert abs(match_1to1(a, b)) < 0.3


# ------------------------------------------------------ vote_frame_results --
CFG = dict(threshold=0.40, consensus_ratio=0.70, frames_min_valid=3)


def fr(ok=True, reason=None, spoof=False, user="budi", sim=0.9, p_real=None):
    return {"ok": ok, "reason": reason, "spoof": spoof, "user": user, "sim": sim,
            "p_real": p_real}


def test_vote_match_konsisten():
    frames = [fr(sim=0.85), fr(sim=0.83), fr(sim=0.87), fr(sim=0.84)]
    out = vote_frame_results(frames, **CFG)
    assert out["status"] == "match"
    assert out["user_id"] == "budi"
    assert out["confidence"] == pytest.approx(0.845)


def test_vote_no_match_skor_rendah():
    frames = [fr(sim=0.20), fr(sim=0.22), fr(sim=0.21)]
    out = vote_frame_results(frames, **CFG)
    assert out["status"] == "no_match"
    assert out["user_id"] is None


def test_vote_no_match_konsensus_pecah():
    # 3 user berbeda -> tidak ada konsensus >= 0.7
    frames = [fr(user="a", sim=0.9), fr(user="b", sim=0.9), fr(user="c", sim=0.9)]
    out = vote_frame_results(frames, **CFG)
    assert out["status"] == "no_match"


def test_vote_spoof():
    frames = [fr(spoof=True, user=None, sim=None, p_real=0.3)] * 3 + [fr(sim=0.9)]
    out = vote_frame_results(frames, **CFG)
    assert out["status"] == "spoof"
    assert out["confidence"] == pytest.approx(0.3)  # mean p_real frame spoof


def test_vote_no_face_dominan():
    frames = [fr(ok=False, reason="no_face")] * 3 + [fr(sim=0.9)]
    out = vote_frame_results(frames, **CFG)
    assert out["status"] == "no_face"


def test_vote_low_quality_dominan():
    frames = [fr(ok=False, reason="blurry(var=10.0)")] * 2 + [fr(sim=0.9)]
    out = vote_frame_results(frames, **CFG)
    assert out["status"] == "low_quality"


def test_vote_kosong():
    out = vote_frame_results([], **CFG)
    assert out["status"] == "no_face"
    assert out["frames_total"] == 0


def test_vote_frame_terlalu_sedikit():
    # 2 frame valid, min 3 -> batch tak sah utk voting (anti enroll foto 1x)
    frames = [fr(sim=0.9), fr(sim=0.9)]
    out = vote_frame_results(frames, **CFG)
    assert out["status"] == "low_quality"
    assert out["frames_valid"] == 2
