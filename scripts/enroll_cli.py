"""CLI enroll: python scripts/enroll_cli.py --user budi --images a.jpg b.jpg ..."""

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
    ap = argparse.ArgumentParser(description="Enroll user ke galeri")
    ap.add_argument("--user", required=True)
    ap.add_argument("--images", nargs="+", required=True)
    ap.add_argument("--min-images", type=int, default=None)
    args = ap.parse_args()

    images = []
    for p in args.images:
        img = cv2.imread(p)
        if img is None:
            print(f"SKIP (tidak terbaca): {p}")
            continue
        images.append(img)

    pipe = VerifyPipeline(load_config())
    summary = pipe.enroll_user(args.user, images, min_images=args.min_images)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["enrolled"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
