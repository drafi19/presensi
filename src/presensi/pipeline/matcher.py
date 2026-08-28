"""Matching embedding (cosine) + voting antar-frame.

Galeri multi-enroll: tiap user punya MATRIX embedding (n, 512) dari n gambar
enroll. Agregasi = MAX cosine terhadap baris-barisnya (robust terhadap variasi
pose antar gambar enroll; DESAIN §5). Semua vektor diasumsikan L2-normalized.
"""

from __future__ import annotations

import numpy as np


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity dua vektor 1-D (fallback aman bila belum normalized)."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return -1.0
    return float(np.dot(a, b) / (na * nb))


def _row_sims(query: np.ndarray, enrolled: np.ndarray) -> np.ndarray:
    """Similarity query vs tiap baris galeri user (1-D atau 2-D)."""
    enrolled = np.asarray(enrolled, dtype=np.float32)
    if enrolled.ndim == 1:
        return np.array([cosine(query, enrolled)], dtype=np.float64)
    # kedua sisi ternormalisasi -> dot product = cosine
    return enrolled @ query


def match_1to1(query: np.ndarray, enrolled: np.ndarray,
               aggregation: str = "max") -> float:
    """Verifikasi 1:1: query vs seluruh embedding user yang diklaim."""
    sims = _row_sims(query, enrolled)
    if aggregation == "mean":
        return float(np.mean(sims))
    return float(np.max(sims))


def match_score(query: np.ndarray,
                gallery: dict[str, np.ndarray]) -> tuple[str | None, float, float]:
    """1:N scan linear. Return (best_user, best_sim, runner_up_sim)."""
    best_user, best_sim, second = None, -1.0, -1.0
    for user_id, enrolled in gallery.items():
        sim = float(np.max(_row_sims(query, enrolled)))
        if sim > best_sim:
            best_user, second, best_sim = user_id, best_sim, sim
        elif sim > second:
            second = sim
    return best_user, best_sim, second


def vote_frame_results(
    frame_results: list[dict],
    threshold: float,
    consensus_ratio: float,
    frames_min_valid: int,
) -> dict:
    """Agregasi hasil per-frame menjadi verdict akhir (kontrak API §7 DESAIN.md).

    Urutan keputusan:
      1. mayoritas frame gagal kualitas  -> no_face / low_quality
      2. >= consensus_ratio frame spoof  -> spoof  (tidak butuh min_valid:
         peringatan spoof tetap dilaporkan walau frame sedikit)
      3. frame valid < frames_min_valid  -> low_quality (batch tak sah utk voting)
      4. median sim >= threshold DAN >= consensus_ratio frame sepakat -> match
      5. selain itu                      -> no_match
    """
    total = len(frame_results)
    if total == 0:
        return {"status": "no_face", "user_id": None, "confidence": None,
                "frames_valid": 0, "frames_total": 0}

    failed = [f for f in frame_results if not f["ok"]]
    if failed and len(failed) / total >= 0.5:
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
        # confidence = p_real rata-rata frame spoof (makin rendah makin yakin spoof)
        p_vals = [f.get("p_real") for f in valid
                  if f.get("spoof") and f.get("p_real") is not None]
        conf = float(np.mean(p_vals)) if p_vals else None
        return {"status": "spoof", "user_id": None, "confidence": conf,
                "frames_valid": n_valid, "frames_total": total}

    if n_valid < frames_min_valid:
        return {"status": "low_quality", "user_id": None, "confidence": None,
                "frames_valid": n_valid, "frames_total": total}

    matched = [f for f in valid if (not f.get("spoof")) and f.get("user")]
    if not matched:
        sims = [f["sim"] for f in valid if f.get("sim") is not None]
        return {"status": "no_match", "user_id": None,
                "confidence": float(np.median(sims)) if sims else None,
                "frames_valid": n_valid, "frames_total": total}

    # konsensus identitas: kandidat yang muncul terbanyak antar frame
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
