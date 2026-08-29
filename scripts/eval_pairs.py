"""Evaluasi identifikasi 1:1 — split per sesi (s1=enroll, s2+=eval).

Skor mengikuti mode deployment (DESAIN §4/§7): tiap embedding evaluasi
dibandingkan ke SET enroll kandidat dgn agregasi MAX.
  genuine  : eval(A) vs enroll(A)  -> skor tinggi diharapkan
  imposter : eval(A) vs enroll(B)  -> skor rendah diharapkan
FAR = % imposter >= t ; FRR = % genuine < t.
Output: statistik pemisahan, EER, threshold utk --target-far, tabel FAR pilihan.

JANGAN dipakai sebagai metrik final sebelum data asli multi-sesi masuk —
lihat docs/PENGUMPULAN_DATA.md.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from presensi.pipeline.verify import VerifyPipeline, load_config  # noqa: E402

IMG_EXT = {".jpg", ".jpeg", ".png"}


def list_images(d: Path) -> list[Path]:
    return sorted(p for p in d.rglob("*") if p.suffix.lower() in IMG_EXT)


def embed_folder(pipe: VerifyPipeline, d: Path) -> tuple[list[np.ndarray], list[str]]:
    embs, rejects = [], []
    for p in list_images(d):
        img = cv2.imread(str(p))
        if img is None:
            rejects.append(f"{p.name}: unreadable")
            continue
        e, reason = pipe.embed_image(img)
        if e is None:
            rejects.append(f"{p.name}: {reason}")
        else:
            embs.append(e)
    return embs, rejects


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluasi FAR/FRR 1:1 (split per sesi)")
    ap.add_argument("--raw", default="data/raw", help="root data/raw/<subjek>/<sesi>/")
    ap.add_argument("--target-far", type=float, default=0.01)
    ap.add_argument("--apply", action="store_true",
                    help="tulis threshold terpilih ke config.yaml")
    args = ap.parse_args()

    raw = Path(args.raw)
    subjects = sorted(d for d in raw.iterdir() if d.is_dir()) if raw.exists() else []
    if len(subjects) < 2:
        print(f"Butuh >=2 subjek di {raw} — baru ada {len(subjects)}. "
              f"Ikuti docs/PENGUMPULAN_DATA.md.")
        return 1

    pipe = VerifyPipeline(load_config())

    enroll: dict[str, np.ndarray] = {}
    evals: dict[str, dict[str, np.ndarray]] = {}
    for subj_dir in subjects:
        subj = subj_dir.name
        sessions = sorted(d for d in subj_dir.iterdir() if d.is_dir())
        for ses in sessions:
            embs, rejects = embed_folder(pipe, ses)
            if rejects:
                print(f"  [{subj}/{ses.name}] {len(rejects)} foto ditolak gate")
            if ses.name == "s1":
                if embs:
                    enroll[subj] = np.stack(embs)
            elif embs:
                evals.setdefault(subj, {})[ses.name] = np.stack(embs)

    missing = [s.name for s in subjects if s.name not in enroll]
    if missing:
        print(f"Subjek tanpa s1 (enroll): {missing} — skip")
    usable = [s.name for s in subjects if s.name in enroll and s.name in evals]
    if len(usable) < 2:
        print("Butuh >=2 subjek dgn enroll(s1) DAN eval(s2+).")
        return 1

    gen_scores: list[float] = []
    imp_scores: list[float] = []
    for a in usable:
        for ses, embs in evals[a].items():
            for e in embs:
                gen_scores.append(float(np.max(enroll[a] @ e)))
                for b in usable:
                    if b != a:
                        imp_scores.append(float(np.max(enroll[b] @ e)))

    gen = np.array(gen_scores)
    imp = np.array(imp_scores)
    grid = np.linspace(0.0, 1.0, 1001)
    far = np.array([np.mean(imp >= t) for t in grid])
    frr = np.array([np.mean(gen < t) for t in grid])
    eer_i = int(np.argmin(np.abs(far - frr)))

    feasible = np.where(far <= args.target_far)[0]
    if len(feasible):
        # feasible terurut naik -> ambil indeks terkecil
        # (threshold terkecil yang sudah memenuhi target FAR -> FRR ikut minimum)
        ti = int(feasible[0])
        t_sel, far_sel, frr_sel = float(grid[ti]), float(far[ti]), float(frr[ti])
    else:
        t_sel, far_sel, frr_sel = None, None, None

    print("\n=== HASIL EVALUASI 1:1 (split per sesi) ===")
    print(f"subjek                 : {len(usable)} {usable}")
    print(f"pasangan genuine       : {len(gen)}")
    print(f"pasangan imposter      : {len(imp)}")
    print(f"genuine  sim mean/med/min : {gen.mean():.3f} / {np.median(gen):.3f} / {gen.min():.3f}")
    print(f"imposter sim mean/med/max : {imp.mean():.3f} / {np.median(imp):.3f} / {imp.max():.3f}")
    print(f"EER                    : {0.5 * (far[eer_i] + frr[eer_i]):.4f} @ t={grid[eer_i]:.3f}")
    print(f"\nThreshold utk target FAR {args.target_far:.2%}: ", end="")
    if t_sel is None:
        print(f"TIDAK TERCAPAI (FAR minimum = {far.min():.4f}) — perlu data/kebijakan lebih")
    else:
        print(f"t={t_sel:.3f}  ->  FAR={far_sel:.4f}  FRR={frr_sel:.4f}")
    print("\nTabel threshold pilihan:")
    for tf in (0.01, 0.001, 0.0001):
        feas = np.where(far <= tf)[0]
        if len(feas):
            i = int(feas[0])
            print(f"  FAR<={tf:.4f}: t={grid[i]:.3f}  FRR={frr[i]:.4f}")
        else:
            print(f"  FAR<={tf:.4f}: tidak tercapai")

    if args.apply and t_sel is not None:
        cfg_path = PROJECT_ROOT / "config.yaml"
        text = cfg_path.read_text(encoding="utf-8")
        text, n1 = re.subn(r"  threshold: [0-9.]+", f"  threshold: {t_sel:.3f}", text, count=1)
        text, n2 = re.subn(
            r"  # placeholder M1[^\n]*",
            f"  # di-set dari eval_pairs.py @ FAR {args.target_far:.2%} "
            f"(FRR {frr_sel:.4f}) — jangan ubah manual", text, count=1)
        if n1:
            cfg_path.write_text(text, encoding="utf-8")
            print(f"\nconfig.yaml diperbarui: threshold={t_sel:.3f}"
                  + (" (komentar placeholder ikut diganti)" if n2 else ""))
        else:
            print("\nGAGAL menulis config (pola tidak ketemu) — set manual.")
    elif args.apply:
        print("\n--apply dilewati: threshold tidak tercapai pada target FAR.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
