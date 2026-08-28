"""CLI verify: python scripts/verify_cli.py --images f1.jpg f2.jpg [-- user budi]

Tanpa --user -> identifikasi 1:N; dengan --user -> verifikasi 1:1.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from presensi.pipeline.verify import VerifyPipeline, load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Verifikasi wajah (batch frame)")
    ap.add_argument("--images", nargs="+", required=True,
                    help="3-10 frame dari rekaman ±2 detik")
    ap.add_argument("--user", default=None,
                    help="klaim user (1:1). Tanpa ini = 1:N")
    args = ap.parse_args()

    frames = []
    for p in args.images:
        img = cv2.imread(p)
        if img is None:
            print(f"SKIP (tidak terbaca): {p}")
            continue
        frames.append(img)

    pipe = VerifyPipeline(load_config())
    verdict, per_frame = pipe.verify_batch(frames, claimed_user=args.user)
    print(json.dumps({"verdict": verdict,
                      "registered_users": sorted(pipe.gallery)},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
