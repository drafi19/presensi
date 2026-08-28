"""Orkestrasi pipeline verifikasi: quality -> detect -> antispoof -> embed -> match.

Config dimuat dari config.yaml di root repo (single source of truth).
Gallery v1 masih in-memory (dict user_id -> embedding); M2 ganti ke storage sqlite/npz.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import yaml

from .antispoof import AntiSpoof
from .detector import FaceEngine
from .matcher import match_1to1, match_score
from ..quality.quality import check_frame, face_too_small

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config(path: Path | None = None) -> dict:
    with open(path or DEFAULT_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class VerifyPipeline:
    """Pipeline verifikasi wajah. Satu instance untuk seluruh lifetime server."""

    def __init__(self, cfg: dict | None = None, config_path: Path | None = None):
        self.cfg = cfg or load_config(config_path)
        models_dir = PROJECT_ROOT / self.cfg["paths"]["models_dir"]

        log.info("Memuat FaceEngine (buffalo_l) ...")
        self.engine = FaceEngine(models_dir, self.cfg.get("pipeline", {}).get("detector"))

        as_cfg = self.cfg["antispoof"]
        model_plan = [(m["name"], m.get("scale")) for m in as_cfg["models"]]
        log.info("Memuat anti-spoof ensemble (%d model) ...", len(model_plan))
        self.antispoof = AntiSpoof(PROJECT_ROOT / as_cfg["model_dir"], model_plan=model_plan)

        self.gallery: dict[str, np.ndarray] = {}  # M2: pindah ke storage module
        self.threshold = float(self.cfg["match"]["threshold"])

    # ------------------------------------------------------------------ #
    def enroll(self, user_id: str, embedding: np.ndarray) -> None:
        """Daftarkan satu embedding ke gallery (in-memory v1)."""
        self.gallery[user_id] = np.asarray(embedding, dtype=np.float32)

    def verify_frame(self, img_bgr: np.ndarray, claimed_user: str | None = None) -> dict:
        """Pipeline lengkap satu frame. Return dict untuk matcher.vote_frame_results."""
        out = {"ok": False, "reason": None, "spoof": None, "user": None, "sim": None,
               "p_real": None}

        # 1) quality gate murah
        ok, reason = check_frame(img_bgr, self.cfg["quality"])
        if not ok:
            out["reason"] = reason
            return out

        # 2) deteksi
        face = self.engine.get_primary_face(img_bgr)
        if face is None:
            out["reason"] = "no_face"
            return out

        x1, y1, x2, y2 = (float(v) for v in face.bbox)
        if face_too_small((int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                          self.cfg["quality"]["face_min_px"]):
            out["reason"] = "face_too_small"
            return out

        # 3) anti-spoof (bbox format x,y,w,h — konvensi referensi)
        label, p_real = self.antispoof.predict(
            img_bgr, (int(x1), int(y1), int(x2 - x1), int(y2 - y1)))
        out["p_real"] = p_real
        if label != 1:  # label 1 = real (aturan resmi referensi)
            out["ok"] = True
            out["spoof"] = True
            return out

        # 4) embedding
        emb = self.engine.embedding(face)
        if emb is None:
            out["reason"] = "embedding_failed"
            return out

        # 5) matching — 1:1 bila ada klaim user (mode utama), else 1:N
        if claimed_user is not None:
            enrolled = self.gallery.get(claimed_user)
            if enrolled is None:
                out["ok"] = True
                out["spoof"] = False
                out["reason"] = "unknown_user"
                return out
            out["ok"] = True
            out["spoof"] = False
            out["user"] = claimed_user
            out["sim"] = match_1to1(emb, enrolled)
            return out

        if not self.gallery:
            out["ok"] = True
            out["spoof"] = False
            out["reason"] = "empty_gallery"
            return out
        best_user, best_sim, _second = match_score(emb, self.gallery)
        out["ok"] = True
        out["spoof"] = False
        out["user"] = best_user
        out["sim"] = best_sim
        return out

    def verify_batch(self, frames: list[np.ndarray],
                     claimed_user: str | None = None) -> tuple[dict, list[dict]]:
        """Batch frame -> verdict voting (kontrak API §7 DESAIN.md)."""
        from .matcher import vote_frame_results

        results = [self.verify_frame(f, claimed_user) for f in frames]
        vcfg = self.cfg["verify"]
        verdict = vote_frame_results(
            results,
            threshold=self.threshold,
            consensus_ratio=float(vcfg["consensus_ratio"]),
            frames_min_valid=int(vcfg["frames_min_valid"]),
        )
        return verdict, results
