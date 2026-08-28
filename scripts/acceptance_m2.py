"""Uji terima M2: enroll 2 orang -> verify benar & salah konsisten + persistensi.

Catatan kejujuran: "variasi" di sini = augmentasi ringan dari 1 foto per orang
(rotasi, skala, pencahayaan) — bukan sesi foto asli. Gambar uji di-upscale agar
wajah melewati gate `face_min_px` (gate ini memang menolak wajah kecil — itu
perilaku benar sistem; data wajah asli multi-sesi datang di M4).
Yang diuji di sini adalah PLUMBING: enroll -> galeri -> verify 1:1/1:N ->
negatif -> persistensi disk via CLI proses terpisah.

Pemakaian: python scripts/acceptance_m2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from presensi.pipeline.verify import VerifyPipeline, load_config  # noqa: E402

TEST_DIR = PROJECT_ROOT / "data" / "test"
AUG_DIR = TEST_DIR / "aug"


def make_variants(path: Path, tag: str, n: int = 5) -> list[Path]:
    """n varian (file JPG): asli, rotasi, skala-crop, gelap, gamma-terang.

    Base di-upscale agar wajah headshot >= gate face_min_px (wajah di sample
    OpenCV ~70-110 px; gate menolak <112 px).
    """
    img = cv2.imread(str(path))
    h, w = img.shape[:2]
    target_min_side = 1400  # headshot lena cukup di 1100; messi (wajah 100px @1100) butuh >=1300
    if min(h, w) < target_min_side:
        fx = target_min_side / min(h, w)
        img = cv2.resize(img, None, fx=fx, fy=fx, interpolation=cv2.INTER_CUBIC)
        # upscale bikin gambar lembut -> variance Laplacian turun -> gate blur
        # menolak (perilaku gate BENAR utk foto asli). Unsharp mask = stand-in
        # utk kamera tajam; amount dipilih TERUKUR (var 14->187, 29->384; semua
        # varian >=60). Catatan: threshold blur gate dikalibrasi per kelas
        # resolusi input saat M4.
        blur = cv2.GaussianBlur(img, (0, 0), 3)
        img = cv2.addWeighted(img, 4.0, blur, -3.0, 0)
        h, w = img.shape[:2]

    out = [img]

    M = cv2.getRotationMatrix2D((w / 2, h / 2), 3.0, 1.0)
    out.append(cv2.warpAffine(img, M, (w, h)))

    big = cv2.resize(img, None, fx=1.25, fy=1.25)
    bh, bw = big.shape[:2]
    out.append(big[(bh - h) // 2:(bh - h) // 2 + h, (bw - w) // 2:(bw - w) // 2 + w])

    out.append(cv2.convertScaleAbs(img, alpha=0.85, beta=0))

    lut = np.array([min(255, int((i / 255.0) ** 0.7 * 255)) for i in range(256)],
                   dtype=np.uint8)
    out.append(cv2.LUT(img, lut))

    AUG_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, im in enumerate(out[:n]):
        p = AUG_DIR / f"{tag}_{i}.jpg"
        cv2.imwrite(str(p), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
        paths.append(p)
    return paths


def main() -> int:
    results: list[tuple[str, bool]] = []

    def check(name: str, cond: bool) -> None:
        results.append((name, bool(cond)))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")

    budi_paths = make_variants(TEST_DIR / "face1.jpg", "budi")
    ani_paths = make_variants(TEST_DIR / "face2.jpg", "ani")
    budi_imgs = [cv2.imread(str(p)) for p in budi_paths]
    ani_imgs = [cv2.imread(str(p)) for p in ani_paths]

    print("== 1. Enroll dua user ==")
    pipe = VerifyPipeline(load_config())
    s_budi = pipe.enroll_user("budi", budi_imgs)
    s_ani = pipe.enroll_user("ani", ani_imgs)
    print(f"  budi: enrolled={s_budi['enrolled']} accepted={s_budi['accepted']} "
          f"rejected={s_budi['rejected']}")
    print(f"  ani : enrolled={s_ani['enrolled']} accepted={s_ani['accepted']} "
          f"rejected={s_ani['rejected']}")
    check("enroll budi sah (>=3 gambar lolos)", s_budi["enrolled"])
    check("enroll ani sah (>=3 gambar lolos)", s_ani["enrolled"])

    print("== 2. Verify positif 1:1 (budi mengaku budi) ==")
    v, _ = pipe.verify_batch(budi_imgs, claimed_user="budi")
    print(f"  {v}")
    check("1:1 positif -> match budi",
          v["status"] == "match" and v["user_id"] == "budi")

    print("== 3. Verify negatif 1:1 (ani mengaku budi) ==")
    v, _ = pipe.verify_batch(ani_imgs, claimed_user="budi")
    print(f"  {v}")
    check("1:1 negatif -> no_match", v["status"] == "no_match")

    print("== 4. Verify 1:N (tanpa klaim) ==")
    v, _ = pipe.verify_batch(ani_imgs)
    print(f"  {v}")
    check("1:N -> match ani", v["status"] == "match" and v["user_id"] == "ani")

    print("== 5. Klaim user tak terdaftar ==")
    v, _ = pipe.verify_batch(budi_imgs, claimed_user="orang_luar")
    print(f"  {v}")
    check("user tak terdaftar -> no_match", v["status"] == "no_match")

    print("== 6. Persistensi: CLI proses terpisah baca galeri dari disk ==")
    import subprocess
    r = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "verify_cli.py"),
         "--user", "budi", "--images"] + [str(p) for p in budi_paths[:3]],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT))
    out = r.stdout or r.stderr
    tail = out.strip().splitlines()
    print("  " + "\n  ".join(tail[-14:]))
    check("proses baru -> match budi (terbaca dari galeri)",
          '"status": "match"' in out and '"user_id": "budi"' in out)

    print("\n== RINGKASAN ==")
    n_ok = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"\n{n_ok}/{len(results)} lulus")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
