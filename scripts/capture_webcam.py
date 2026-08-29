"""Capture foto dari webcam utk sesi pengumpulan data (protokol M4).

Preview live; tekan SPACE = jepret, q = berhenti.
Berhenti otomatis saat target tercapai. Nama file: {prefix}_{urut:03d}.jpg

Pemakaian:
  uv run python scripts/capture_webcam.py --list                     # cek kamera
  uv run python scripts/capture_webcam.py --out data/raw/rafi/s1 --count 8
  uv run python scripts/capture_webcam.py --camera 1 --out data/spoof/print/rafi --count 10

Ketahanan: resolusi 1280x720 diminta SEBELUM read pertama (perubahan resolusi
di tengah stream bikin MSMF rusak); bila 720p gagal -> fallback ke native;
read dibungkus try + auto-reopen.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

try:  # redam log C++ (WARN/ERROR obsensor/MSMF) bila tersedia
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:  # noqa: BLE001
    pass

_BACKENDS = [(cv2.CAP_MSMF, "MSMF"), (cv2.CAP_ANY, "ANY")]
_REQ_SIZE = (1280, 720)


def _try_open(idx: int, size: tuple[int, int] | None):
    """Buka kamera idx, set resolusi SEBELUM read pertama, uji 1 frame."""
    for backend, _name in _BACKENDS:
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            cap.release()
            continue
        if size is not None:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        try:
            ok, frame = cap.read()
        except cv2.error:
            ok, frame = False, None
        if ok and frame is not None:
            return cap
        cap.release()
    return None


def start_camera(preferred: int) -> tuple[cv2.VideoCapture | None, int, tuple[int, int]]:
    """Dua-pass: minta 720p dulu; bila tak ada yang jalan, pakai resolusi native."""
    candidates = [preferred] + [i for i in range(4) if i != preferred]
    # pass 1: 720p
    for i in candidates:
        cap = _try_open(i, _REQ_SIZE)
        if cap is not None:
            return cap, i, _REQ_SIZE
    # pass 2: native
    for i in candidates:
        cap = _try_open(i, None)
        if cap is not None:
            return cap, i, (0, 0)
    return None, -1, (0, 0)


def list_cameras() -> list[int]:
    active = []
    for i in range(4):
        cap, found, _size = start_camera(i)
        if cap is not None:
            if found == i:  # fallback diabaikan — kamera asli tercantum di iterasinya
                active.append(found)
                ok, frame = cap.read()
                if ok and frame is not None:
                    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    print(f"camera[{found}]: {frame.shape[1]}x{frame.shape[0]} mean={g.mean():.0f}  <-- AKTIF")
            cap.release()
    return active


def main() -> int:
    ap = argparse.ArgumentParser(description="Capture webcam -> JPEG")
    ap.add_argument("--out", default=None, help="folder tujuan (dibuat bila belum ada)")
    ap.add_argument("--count", type=int, default=8, help="target jumlah foto")
    ap.add_argument("--camera", type=int, default=0, help="index kamera (auto-fallback bila gagal)")
    ap.add_argument("--prefix", default="img")
    ap.add_argument("--list", action="store_true", help="hanya enumerasi kamera")
    args = ap.parse_args()

    if args.list:
        active = list_cameras()
        print("aktif:", active if active else "TIDAK ADA")
        return 0 if active else 1
    if not args.out:
        ap.error("--out wajib kecuali memakai --list")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cap, actual, size = start_camera(args.camera)
    if cap is None:
        print("GAGAL: tidak ada kamera yang bisa dibuka (dicoba 0..3)")
        return 1
    if actual != args.camera:
        print(f"catatan: kamera {args.camera} gagal — pakai kamera {actual} (auto-fallback)")
    print(f"resolusi: {size[0]}x{size[1]}" if size[0] else "resolusi: native")

    n = 0
    print(f"Target {args.count} foto -> {out_dir}  (kamera {actual})")
    print("SPACE = jepret | q = keluar")
    while n < args.count:
        try:
            ok, frame = cap.read()
        except cv2.error as e:
            print(f"  read error: {e.msg[:80]} — reopen kamera...")
            cap.release()
            cap, actual, size = start_camera(actual)
            if cap is None:
                print("GAGAL: kamera tidak bisa dibuka ulang")
                break
            continue
        if not ok or frame is None:
            print("  frame kosong — diulang...")
            continue
        disp = frame.copy()
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
