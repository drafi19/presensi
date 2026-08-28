"""Smoke test M1: satu foto -> deteksi + embedding 512-d + verdict anti-spoof.

Pemakaian:
    python scripts/smoke_test.py --image path/ke/foto.jpg

Keluaran yang diharapkan (kriteria M1):
    - embedding: dim=512, L2 norm ~= 1.0
    - anti-spoof: label real/spoof + p_real tercetak
    - timing per stage tercetak
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from presensi.pipeline.verify import VerifyPipeline, load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Smoke test pipeline M1")
    ap.add_argument("--image", required=True, help="path foto uji (wajah)")
    ap.add_argument("--no-spoof", action="store_true",
                    help="lewati stage anti-spoof (debug cepat)")
    args = ap.parse_args()

    img = cv2.imread(str(Path(args.image)))
    if img is None:
        print(f"GAGAL: tidak bisa membaca gambar {args.image}")
        return 1
    print(f"Gambar: {args.image}  shape={img.shape}")

    cfg = load_config()
    t0 = time.perf_counter()
    pipe = VerifyPipeline(cfg)
    print(f"Model dimuat dalam {time.perf_counter() - t0:.1f}s")

    # --- stage-by-stage (untuk timing per stage) ---
    from presensi.quality.quality import check_frame

    t = time.perf_counter()
    ok, reason = check_frame(img, cfg["quality"])
    print(f"[quality ] ok={ok} reason={reason}  ({(time.perf_counter()-t)*1000:.0f} ms)")
    if not ok:
        return 1

    t = time.perf_counter()
    face = pipe.engine.get_primary_face(img)
    print(f"[detect  ] {'terdeteksi' if face is not None else 'TIDAK ADA'}"
          f"  ({(time.perf_counter()-t)*1000:.0f} ms)")
    if face is None:
        return 1
    x1, y1, x2, y2 = (float(v) for v in face.bbox)
    print(f"           bbox=({x1:.0f},{y1:.0f},{x2:.0f},{y2:.0f}) det_score={face.det_score:.3f}")

    if not args.no_spoof:
        t = time.perf_counter()
        label, p_real = pipe.antispoof.predict(
            img, (int(x1), int(y1), int(x2 - x1), int(y2 - y1)))
        verdict = "REAL" if label == 1 else "SPOOF"
        print(f"[spoof   ] label={label} -> {verdict}  p_real={p_real:.3f}"
              f"  ({(time.perf_counter()-t)*1000:.0f} ms)")
        print("           catatan: pretrained anti-spoof pada wajah sintetis/"
              "layar bisa terdeteksi spoof — itu perilaku benar, bukan bug.")

    t = time.perf_counter()
    emb = pipe.engine.embedding(face)
    if emb is None:
        print("[embed   ] GAGAL")
        return 1
    print(f"[embed   ] dim={emb.shape[0]}  L2norm={np.linalg.norm(emb):.4f}"
          f"  ({(time.perf_counter()-t)*1000:.0f} ms)")

    # --- end-to-end via API internal pipeline ---
    t = time.perf_counter()
    verdict, results = pipe.verify_batch([img])
    ms = (time.perf_counter() - t) * 1000
    print(f"[verify  ] end-to-end 1 frame: {ms:.0f} ms")
    print(f"           verdict={verdict}")
    print(f"           per-frame={results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
