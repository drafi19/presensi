"""Galeri embedding: SQLite (metadata) + NPZ (vektor 512-d).

Sesuai DESAIN.md §2: SQLite = sumber kebenaran metadata (user_id,
model_version, jumlah gambar); NPZ = penyimpanan vektor.
Key NPZ = hash pendek user_id (hindari masalah karakter pada nama entry zip).
Aturan model_version: galery dibuat dengan backbone X HANYA berisi embedding
dari backbone X — buka dengan model_version berbeda = error (wajib re-enroll).
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import time
from pathlib import Path

import numpy as np

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrollments (
  user_id       TEXT PRIMARY KEY,
  npz_key       TEXT NOT NULL UNIQUE,
  model_version TEXT NOT NULL,
  n_images      INTEGER NOT NULL,
  n_embeddings  INTEGER NOT NULL,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);
"""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _npz_key(user_id: str) -> str:
    return hashlib.sha1(user_id.encode("utf-8")).hexdigest()[:16]


class GalleryStore:
    """Buka galeri di `data_dir`. Satu instance untuk seluruh lifetime proses."""

    def __init__(self, data_dir: Path | str, model_version: str,
                 strict_version: bool = True):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "gallery.db"
        self.npz_path = self.data_dir / "gallery.npz"
        self.model_version = model_version
        self.strict_version = strict_version

        self._conn = sqlite3.connect(self.db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        if strict_version:
            self._check_version_consistency()

    def _check_version_consistency(self) -> None:
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM enrollments WHERE model_version != ?",
            (self.model_version,))
        n = cur.fetchone()[0]
        if n:
            raise ValueError(
                f"Galeri berisi {n} enrollment dengan model_version berbeda "
                f"daripada '{self.model_version}'. Embedding antar-backbone tidak "
                f"comparable — hapus galeri atau re-enroll (DESAIN §5).")

    # -------------------------------------------------------------- tulis ---
    def upsert(self, user_id: str, embeddings: np.ndarray, n_images: int) -> None:
        """Timpa seluruh embedding milik `user_id` dengan `embeddings` (n,512)."""
        emb = np.asarray(embeddings, dtype=np.float32)
        if emb.ndim == 1:
            emb = emb.reshape(1, -1)

        data: dict[str, np.ndarray] = {}
        if self.npz_path.exists():
            with np.load(self.npz_path) as z:
                data = {k: z[k] for k in z.files}
        key = _npz_key(user_id)
        data[key] = emb

        tmp = self.npz_path.with_suffix(".tmp")
        with open(tmp, "wb") as f:  # file object agar nama tmp dipertahankan
            np.savez(f, **data)
        os.replace(tmp, self.npz_path)  # atomic

        now = _now()
        self._conn.execute(
            "INSERT INTO enrollments (user_id, npz_key, model_version, n_images,"
            " n_embeddings, created_at, updated_at) VALUES (?,?,?,?,?,?,?)"
            " ON CONFLICT(user_id) DO UPDATE SET npz_key=excluded.npz_key,"
            " model_version=excluded.model_version, n_images=excluded.n_images,"
            " n_embeddings=excluded.n_embeddings, updated_at=excluded.updated_at",
            (user_id, key, self.model_version, int(n_images), int(emb.shape[0]),
             now, now))
        self._conn.commit()

    def delete(self, user_id: str) -> bool:
        cur = self._conn.execute("SELECT npz_key FROM enrollments WHERE user_id=?",
                                 (user_id,))
        row = cur.fetchone()
        if row is None:
            return False
        self._conn.execute("DELETE FROM enrollments WHERE user_id=?", (user_id,))
        self._conn.commit()
        if self.npz_path.exists():
            with np.load(self.npz_path) as z:
                data = {k: z[k] for k in z.files if k != row[0]}
            tmp = self.npz_path.with_suffix(".tmp")
            with open(tmp, "wb") as f:
                np.savez(f, **data)
            os.replace(tmp, self.npz_path)
        return True

    # --------------------------------------------------------------- baca ---
    def list_users(self) -> list[str]:
        cur = self._conn.execute(
            "SELECT user_id FROM enrollments ORDER BY user_id")
        return [r[0] for r in cur.fetchall()]

    def get(self, user_id: str) -> np.ndarray | None:
        cur = self._conn.execute(
            "SELECT npz_key FROM enrollments WHERE user_id=?", (user_id,))
        row = cur.fetchone()
        if row is None or not self.npz_path.exists():
            return None
        with np.load(self.npz_path) as z:
            return z[row[0]] if row[0] in z.files else None

    def load_all(self) -> dict[str, np.ndarray]:
        """Semua user -> matrix embedding (n,512). Dipakai pipeline saat start."""
        out: dict[str, np.ndarray] = {}
        if not self.npz_path.exists():
            return out
        cur = self._conn.execute("SELECT user_id, npz_key FROM enrollments")
        with np.load(self.npz_path) as z:
            for user_id, key in cur.fetchall():
                if key in z.files:
                    out[user_id] = z[key]
        return out

    def close(self) -> None:
        self._conn.close()
