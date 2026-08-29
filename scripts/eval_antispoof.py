"""Evaluasi anti-spoof (MiniFASNet ensemble) pada data serangan & bona fide.

Data (protokol docs/PENGUMPULAN_DATA.md):
  data/spoof/print/  data/spoof/screen/   -> serangan (harus dideteksi spoof)
  data/raw/<subjek>/s2|s3/...             -> bona fide (harus lolos sebagai real)

Metrik: TPR (attack tertangkap), TNR (bona fide lolos), FPR (bona fide salah
ditandai spoof). FPR tinggi = user beneran susah presensi; TPR rendah =
sistem mudah dibohongi. Keduanya dilaporkan apa adanya.

Pemakaian: python scripts/eval_antispoof.py --spoof data/spoof --raw data/raw
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from presensi.pipeline.verify import VerifyPipeline, load_config  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png"}


def list_images(d: Path) -> list[Path]:
    return sorted(p for p in d.rglob("*") if p.suffix.lower() in IMG_EXT)


def face_bbox_or_none(pipe: VerifyPipeline, img):
    face = pipe.engine.get_primary_face(img)
    if face is None:
        return None
    x1, y1, x2, y2 = (float(v) for v in face.bbox)
    return (int(x1), int(y1), int(x2 - x1), int(y2 - y1))


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluasi anti-spoof")
    ap.add_argument("--spoof", default="data/spoof",
                    help="root serangan: <root>/print/, <root>/screen/ (wajib)")
    ap.add_argument("--raw", default="data/raw",
                    help="root bona fide: data/raw/<subjek>/s2.. (sesi non-enroll)")
    args = ap.parse_args()

    pipe = VerifyPipeline(load_config())
    results: list[tuple[str, bool, float]] = []  # (kategori, is_attack, p_real)

    spoof_root = Path(args.spoof)
    if spoof_root.exists():
        for attack_dir in sorted(d for d in spoof_root.iterdir() if d.is_dir()):
            for p in list_images(attack_dir):
                img = cv2.imread(str(p))
                if img is None:
                    continue
                bbox = face_bbox_or_none(pipe, img)
                if bbox is None:
                    print(f"  [spoof/{attack_dir.name}] {p.name}: wajah tak terdeteksi (skip)")
                    continue
                _label, p_real = pipe.antispoof.predict(img, bbox)
                results.append((f"spoof/{attack_dir.name}", True, p_real))
    else:
        print(f"PERINGATAN: {spoof_root} tidak ada — data serangan wajib utk metrik ini.")

    raw = Path(args.raw)
    n_bona = 0
    if raw.exists():
        for subj in sorted(d for d in raw.iterdir() if d.is_dir()):
            for ses in sorted(d for d in subj.iterdir() if d.is_dir()):
                if ses.name == "s1":  # s1 = enroll, tidak masuk evaluasi
                    continue
                for p in list_images(ses):
                    img = cv2.imread(str(p))
                    if img is None:
                        continue
                    bbox = face_bbox_or_none(pipe, img)
                    if bbox is None:
                        continue
                    _label, p_real = pipe.antispoof.predict(img, bbox)
                    results.append((f"bona_fide/{subj.name}/{ses.name}", False, p_real))
                    n_bona += 1

    if not results:
        print("Tidak ada data yang bisa dievaluasi.")
        return 1

    print("\n=== EVALUASI ANTI-SPOOF (threshold real:", end=" ")
    print(f"{load_config()['antispoof']['real_threshold']}) ===")
    per_cat: dict[str, list[tuple[bool, float]]] = {}
    for cat, is_attack, p_real in results:
        per_cat.setdefault(cat, []).append((is_attack, p_real))

    tpr_n = tpr_d = 0
    for cat in sorted(per_cat):
        vals = per_cat[cat]
        is_attack = vals[0][0]
        if is_attack:
            caught = sum(1 for _, p in vals if p < load_config()["antispoof"]["real_threshold"])
            tpr_n += caught
            tpr_d += len(vals)
            print(f"  {cat:35} n={len(vals):3d}  TERTANGKAP {caught} ({caught/len(vals):.1%})")
        else:
            passed = sum(1 for _, p in vals if p >= load_config()["antispoof"]["real_threshold"])
            print(f"  {cat:35} n={len(vals):3d}  LOLOS {passed} ({passed/len(vals):.1%})")

    bona = [(p, cat) for cat, vals in per_cat.items() for is_a, p in vals if not is_a]
    if bona and tpr_d:
        fpr = sum(1 for p, _ in bona if p < load_config()["antispoof"]["real_threshold"])
        tnr = len(bona) - fpr
        print(f"\nTPR (attack tertangkap) : {tpr_n}/{tpr_d} = {tpr_n/tpr_d:.1%}")
        print(f"TNR (bona fide lolos)   : {tnr}/{len(bona)} = {tnr/len(bona):.1%}")
        print(f"FPR (bona fide ditandai): {fpr}/{len(bona)} = {fpr/len(bona):.1%}")
        print("\nCatatan: FPR tinggi -> user asli terganggu (tuning real_threshold /")
        print("fine-tune model); TPR rendah -> serangan lolos (perkuat defense).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
