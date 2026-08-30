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
from ..storage.gallery import GalleryStore
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

        self.store = GalleryStore(
            PROJECT_ROOT / self.cfg["paths"]["gallery_dir"],
            model_version=self.cfg["project"]["model_version"],
        )
        self.gallery = self.store.load_all()  # user_id -> matrix (n, 512)
        self.threshold = float(self.cfg["match"]["threshold"])
        self.aggregation = self.cfg["match"].get("aggregation", "max")

    # ------------------------------------------------------------------ #
    def enroll_user(self, user_id: str, images: list[np.ndarray],
                    min_images: int | None = None) -> dict:
        """Enroll: tiap gambar lewat quality+detect(1 wajah)+antispoof+embed.

        Gambar ditolak satu-satu dengan alasan eksplisit (kontrak §7); enroll
        sah bila >= min_images gambar lolos (DESAIN §5). Gagal total tidak
        mengubah galeri.
        """
        min_required = int(min_images or self.cfg["enroll"]["min_images"])
        accepted: list[np.ndarray] = []
        rejected: list[dict] = []

        for idx, img in enumerate(images):
            emb, reason = self.embed_image(img)
            if emb is None:
                rejected.append({"index": idx, "reason": reason})
            else:
                accepted.append(emb)

        summary = {
            "user_id": user_id,
            "enrolled": False,
            "accepted": len(accepted),
            "min_required": min_required,
            "rejected": rejected,
            "model_version": self.cfg["project"]["model_version"],
        }
        if len(accepted) < min_required:
            return summary

        embs = np.stack(accepted).astype(np.float32)
        self.store.upsert(user_id, embs, n_images=len(images))
        self.gallery[user_id] = embs
        summary["enrolled"] = True
        summary["n_embeddings"] = int(embs.shape[0])
        return summary

    def embed_image(self, img: np.ndarray) -> tuple[np.ndarray | None, str | None]:
        """Satu gambar -> (embedding, None) atau (None, reason).

        Gerbang lengkap utk ENROLL & evaluasi: quality -> detect (harus tepat
        1 wajah) -> face_too_small -> anti-spoof -> embed.
        (verify_frame beda aturan: boleh multi-wajah, ambil wajah terbesar.)
        """
        ok, reason = check_frame(img, self.cfg["quality"])
        if not ok:
            return None, reason or "low_quality"

        faces = self.engine.detect(img)
        if not faces:
            return None, "no_face"
        if len(faces) > 1:
            return None, "multiple_faces"
        face = faces[0]

        x1, y1, x2, y2 = (float(v) for v in face.bbox)
        if face_too_small((int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
                          self.cfg["quality"]["face_min_px"]):
            return None, "face_too_small"

        label, p_real = self.antispoof.predict(
            img, (int(x1), int(y1), int(x2 - x1), int(y2 - y1)))
        if label != 1:
            return None, f"spoof(p_real={p_real:.2f})"

        emb = self.engine.embedding(face)
        if emb is None:
            return None, "embedding_failed"
        return emb, None

    def reload_gallery(self) -> int:
        """Baca ulang galeri dari disk (panggil tiap verify — CLI/API lain bisa
        menulis galeri kapan saja). Return jumlah user."""
        self.gallery = self.store.load_all()
        return len(self.gallery)

    def remove_user(self, user_id: str) -> bool:
        """Hapus user dari galeri (disk + memori). Return True bila ada."""
        ok = self.store.delete(user_id)
        self.gallery.pop(user_id, None)
        return ok

    def user_info(self, user_id: str) -> dict | None:
        return self.store.get_meta(user_id)

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
            out["sim"] = match_1to1(emb, enrolled, aggregation=self.aggregation)
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
