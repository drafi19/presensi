"""Unit test GalleryStore (SQLite + NPZ) — embedding sintetis, tanpa model."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from presensi.storage.gallery import GalleryStore  # noqa: E402


def mat(seed: int, n: int = 3) -> np.ndarray:
    v = np.random.default_rng(seed).normal(size=(n, 512)).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


@pytest.fixture()
def store(tmp_path: Path):
    s = GalleryStore(tmp_path, model_version="buffalo_l")
    yield s
    s.close()


def test_upsert_dan_load_all(store: GalleryStore):
    store.upsert("budi", mat(1), n_images=3)
    store.upsert("ani", mat(2), n_images=4)
    gal = store.load_all()
    assert set(gal) == {"budi", "ani"}
    assert gal["budi"].shape == (3, 512)
    # ternormalisasi
    assert np.allclose(np.linalg.norm(gal["budi"], axis=1), 1.0, atol=1e-5)


def test_upsert_timpa(store: GalleryStore):
    store.upsert("budi", mat(1), n_images=3)
    store.upsert("budi", mat(9, n=2), n_images=5)
    gal = store.load_all()
    assert gal["budi"].shape == (2, 512)
    row = store._conn.execute(
        "SELECT n_images, n_embeddings FROM enrollments WHERE user_id='budi'"
    ).fetchone()
    assert row == (5, 2)


def test_get_dan_delete(store: GalleryStore):
    store.upsert("budi", mat(1), n_images=3)
    assert store.get("budi") is not None
    assert store.delete("budi") is True
    assert store.get("budi") is None
    assert store.delete("budi") is False  # sudah tidak ada
    assert store.load_all() == {}


def test_list_users(store: GalleryStore):
    store.upsert("zaki", mat(3), n_images=1)
    store.upsert("ani", mat(4), n_images=1)
    assert store.list_users() == ["ani", "zaki"]  # urut alfabet


def test_version_conflict(tmp_path: Path):
    s1 = GalleryStore(tmp_path, model_version="buffalo_l")
    s1.upsert("budi", mat(1), n_images=3)
    s1.close()
    with pytest.raises(ValueError, match="re-enroll"):
        GalleryStore(tmp_path, model_version="backbone_lain")


def test_npz_key_stabil(store: GalleryStore):
    from presensi.storage.gallery import _npz_key
    assert _npz_key("budi") == _npz_key("budi")
    assert _npz_key("budi") != _npz_key("ani")
