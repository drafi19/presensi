"""Matching embedding (cosine) + voting antar-frame."""

from __future__ import annotations

import numpy as np


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity untuk vektor ternormalisasi L2 (fallback: hitung manual)."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return -1.0
    return float(np.dot(a, b) / (na * nb))


def match_score(query: np.ndarray, gallery: dict[str, np.ndarray]) -> tuple[str | None, float, float]:
    """1:N scan linear.

    Return (best_user, best_sim, runner_up_sim). runner_up dipakai untuk
    margin analysis pada mode 1:N (v1 fokus 1:1).
    """
    best_user, best_sim, second = None, -1.0, -1.0
    for user_id, emb in gallery.items():
        sim = cosine(query, emb)
        if sim > best_sim:
            best_user, second, best_sim = user_id, best_sim, sim
        elif sim > second:
            second = sim
    return best_user, best_sim, second


def match_1to1(query: np.ndarray, enrolled: np.ndarray) -> float:
    """Verifikasi 1:1: similarity query vs embedding user yang diklaim."""
    return cosine(query, enrolled)


def vote_frame_results(
    frame_results: list[dict],
    threshold: float,
    consensus_ratio: float,
    frames_min_valid: int,
) -> dict:
    """Agregasi hasil per-frame menjadi verdict akhir.

    frame_results: list dari pipeline.verify._process_frame()
      {"ok": bool, "reason": str|None, "spoof": bool|None, "user": str|None, "sim": float|None}

    Verdict (kontrak API §7 DESAIN.md):
      no_face / low_quality : gagal kualitas dominan
      spoof                 : >= consensus_ratio frame terdeteksi spoof
      match                 : median sim >= threshold DAN >= consensus_ratio frame
                              valid sepakat user sama
      no_match              : frame valid cukup tapi skor di bawah threshold
    """
    total = len(frame_results)
    if total == 0:
        return {"status": "no_face", "user_id": None, "confidence": None,
                "frames_valid": 0, "frames_total": 0}

    failed = [f for f in frame_results if not f["ok"]]
    if failed and len(failed) / total >= 0.5:
        # mayoritas frame gagal kualitas -> laporkan reason pertama yang dominan
        reasons = [f["reason"] or "unknown" for f in failed]
        dominant = max(set(reasons), key=reasons.count)
        status = "no_face" if "no_face" in dominant else "low_quality"
        return {"status": status, "user_id": None, "confidence": None,
                "frames_valid": 0, "frames_total": total}

    valid = [f for f in frame_results if f["ok"]]
    n_valid = len(valid)
    if n_valid == 0:
        return {"status": "no_face", "user_id": None, "confidence": None,
                "frames_valid": 0, "frames_total": total}

    n_spoof = sum(1 for f in valid if f.get("spoof"))
    if n_spoof / n_valid >= consensus_ratio:
        # skor spoof = proporsi frame real (semakin tinggi semakin meyakinkan real)
        return {"status": "spoof", "user_id": None,
                "confidence": float(1.0 - n_spoof / n_valid),
                "frames_valid": n_valid, "frames_total": total}

    matched = [f for f in valid if (not f.get("spoof")) and f.get("user")]
    if not matched:
        sims = [f["sim"] for f in valid if f.get("sim") is not None]
        return {"status": "no_match", "user_id": None,
                "confidence": float(np.median(sims)) if sims else None,
                "frames_valid": n_valid, "frames_total": total}

    # kandidat terbanyak antar frame (konsensus identitas)
    users = [f["user"] for f in matched]
    counts = {u: users.count(u) for u in set(users)}
    best_user = max(counts, key=counts.get)
    agree = counts[best_user] / n_valid

    sims = [f["sim"] for f in matched if f["user"] == best_user]
    med = float(np.median(sims))

    if med >= threshold and agree >= consensus_ratio:
        return {"status": "match", "user_id": best_user, "confidence": med,
                "frames_valid": n_valid, "frames_total": total}
    return {"status": "no_match", "user_id": None, "confidence": med,
            "frames_valid": n_valid, "frames_total": total}
