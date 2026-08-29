"""Ekstrak frame dari video rekaman presensi -> batch JPEG utk verify.

Meniru cara mobile app akan mengambil frame (protokol DESAIN §4): 1 frame
per ~0.3 detik, maksimum 10 frame.

Pemakaian: python scripts/extract_frames.py --video rekaman.mp4 --out data/frames
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

DEFAULT_INTERVAL_S = 0.3
DEFAULT_MAX = 10


def main() -> int:
    ap = argparse.ArgumentParser(description="Video -> frame batch")
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S,
                    help=f"detik antar frame (default {DEFAULT_INTERVAL_S})")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX,
                    help=f"maksimum frame (default {DEFAULT_MAX})")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"GAGAL buka video: {args.video}")
        return 1
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(round(fps * args.interval)))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    idx = 0
    while saved < args.max:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0:
            p = out_dir / f"frame_{saved:03d}.jpg"
            cv2.imwrite(str(p), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
            saved += 1
        idx += 1
    cap.release()
    print(f"{saved} frame -> {out_dir} (fps={fps:.1f}, interval={args.interval}s)")
    return 0 if saved else 1


if __name__ == "__main__":
    raise SystemExit(main())
