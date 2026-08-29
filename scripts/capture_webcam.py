"""Capture foto dari webcam utk sesi pengumpulan data (protokol M4).

Preview live; tekan SPACE = jepret, q = berhenti.
Berhenti otomatis saat target tercapai. Nama file: {prefix}_{urut:03d}.jpg

Pemakaian:
  uv run python scripts/capture_webcam.py --out data/raw/rafi/s1 --count 8
  uv run python scripts/capture_webcam.py --out data/spoof/print/rafi --count 10
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2


def main() -> int:
    ap = argparse.ArgumentParser(description="Capture webcam -> JPEG")
    ap.add_argument("--out", required=True, help="folder tujuan (dibuat bila belum ada)")
    ap.add_argument("--count", type=int, default=8, help="target jumlah foto")
    ap.add_argument("--camera", type=int, default=0, help="index kamera (default 0)")
    ap.add_argument("--prefix", default="img")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"GAGAL: kamera {args.camera} tidak bisa dibuka")
        return 1
    # resolusi menyegarkan: minta besar, jangan set kecil
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    n = 0
    print(f"Target {args.count} foto -> {out_dir}")
    print("SPACE = jepret | q = keluar")
    while n < args.count:
        ok, frame = cap.read()
        if not ok:
            print("GAGAL: frame tidak terbaca")
            break
        disp = frame.copy()
        h, w = disp.shape[:2]
        cv2.putText(disp, f"{n}/{args.count}  SPACE=jepret  q=keluar",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("capture", disp)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord(" "):
            n += 1
            p = out_dir / f"{args.prefix}_{n:03d}.jpg"
            cv2.imwrite(str(p), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            print(f"  {p}")
    cap.release()
    cv2.destroyAllWindows()
    print(f"Selesai: {n} foto di {out_dir}")
    print(f"Segera validasi: uv run python scripts/collect_data.py --check {out_dir}")
    return 0 if n >= args.count else 1


if __name__ == "__main__":
    raise SystemExit(main())
