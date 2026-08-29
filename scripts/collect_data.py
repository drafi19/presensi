"""Validasi data M4 (protokol: docs/PENGUMPULAN_DATA.md).

Mode:
  --check <dir>   cek tiap foto dgn gate penuh (OK/ditolak+alasan) — pakai saat sesi foto
  --tree <dir>    rekap jumlah foto per subjek/sesi vs target protokol

Contoh:
  python scripts/collect_data.py --check data/raw/rafi/s1
  python scripts/collect_data.py --tree data/raw
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from presensi.pipeline.verify import VerifyPipeline, load_config  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png"}
TARGET = {"enroll_s1": 8, "eval_per_sesi": 10, "spoof_per_jenis": 10, "min_subjek": 4}


def list_images(d: Path) -> list[Path]:
    return sorted(p for p in d.rglob("*") if p.suffix.lower() in IMG_EXT)


def main() -> int:
    ap = argparse.ArgumentParser(description="Validasi data pengumpulan M4")
    ap.add_argument("--check", help="folder foto: cek per-file dgn gate pipeline")
    ap.add_argument("--tree", help="root data (raw/spoof): rekap jumlah vs target")
    ap.add_argument("--strict", action="store_true",
                    help="exit 1 bila ada foto ditolak (mode --check)")
    args = ap.parse_args()
    if not args.check and not args.tree:
        ap.error("pilih --check atau --tree")

    pipe = VerifyPipeline(load_config()) if args.check else None

    if args.check:
        root = Path(args.check)
        files = list_images(root) if root.is_dir() else ([root] if root.exists() else [])
        if not files:
            print(f"Tidak ada gambar di {root}")
            return 1
        n_ok = n_rej = 0
        for p in files:
            img = cv2.imread(str(p))
            if img is None:
                print(f"  {p.name:30} GAGAL BACA")
                n_rej += 1
                continue
            _emb, reason = pipe.embed_image(img)
            if reason is None:
                print(f"  {p.name:30} OK")
                n_ok += 1
            else:
                print(f"  {p.name:30} DITOLAK: {reason}")
                n_rej += 1
        print(f"\n{n_ok} OK / {n_rej} ditolak dari {len(files)} foto")
        return 1 if (args.strict and n_rej) else 0

    # --tree
    root = Path(args.tree)
    if not root.exists():
        print(f"Folder tidak ada: {root}")
        return 1
    counts: dict[str, int] = defaultdict(int)
    for p in list_images(root):
        rel = p.relative_to(root)
        parts = rel.parts
        key = "/".join(parts[:-1]) if len(parts) > 1 else "(root)"
        counts[key] += 1

    print(f"{'folder':45} n   target")
    subjects = set()
    for k in sorted(counts):
        target = ""
        parts = k.split("/")
        if len(parts) >= 2 and parts[-1].startswith("s"):
            subjects.add(parts[0])
            target = str(TARGET["enroll_s1" if parts[-1] == "s1" else "eval_per_sesi"])
        elif "spoof" in k:
            target = str(TARGET["spoof_per_jenis"])
        print(f"  {k:43} {counts[k]:3d}  {target}")
    print(f"\nSubjek terdeteksi: {len(subjects)} (minimal {TARGET['min_subjek']})")
    short = [k for k, v in counts.items() if v < 3]
    if short:
        print(f"Perhatian (n<3, tak layak dipakai): {short}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
