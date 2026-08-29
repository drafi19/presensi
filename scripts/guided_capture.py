"""Guided capture — pengumpulan data otomatis per pose (protokol M4).

Kamera mengarahkan subjek pose demi pose (teks besar di layar + metrik live);
foto DIJEPRET OTOMATIS saat pose tercapai & stabil (6 frame berturut-turut)
dan lolos gate penuh (quality -> wajah tunggal -> ukuran -> anti-spoof).
Gagal gate = pose itu diulang otomatis.

Pose terbagi: WAJIB (geometris — selalu bisa dilakukan) dan OPSIONAL
(cahaya/ekstrem — dilewati dengan `s` bila lingkungan tak memungkinkan,
mis. siang hari tak bisa meredupkan lampu; variasi cahaya alami antar-hari
pada s2/s3 tetap terekam). SPACE = jepret manual (darurat), q = keluar.
File yang tersimpan DIJAMIN lolos semua gate.

Pemakaian:
  uv run python scripts/guided_capture.py --mode enroll --subject amin --session s1
  uv run python scripts/guided_capture.py --mode eval --subject amin --session s2
  uv run python scripts/guided_capture.py --mode spoof --attack print --subject amin
  uv run python scripts/guided_capture.py --list
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

import cv2

try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:  # noqa: BLE001
    pass

import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from presensi.pipeline.verify import VerifyPipeline, load_config  # noqa: E402

# ---------------------------------------------------------------- konstanta ---
# Threshold di-longgarkan (feedback sesi nyata); kalibrasi final di M4c.
STREAK_NEEDED = 6       # frame berturut-turut memenuhi kondisi sebelum jepret
COOLDOWN_S = 1.0        # jeda setelah jepret
ROLL_TILT = 6.0         # derajat; ambang "condong"
ROLL_STRAIGHT = 15.0    # derajat; ambang "tegak"
W_BACK = 0.70           # mundur: lebar wajah < 70% baseline
W_NEAR = 1.15           # dekat: lebar wajah > 115% baseline
B_BRIGHT = 1.05         # terang: brightness > 105% baseline  (opsional)
B_DIM = 0.72            # remang: brightness < 72% baseline     (opsional)
B_DIM_HARD = 0.55       # remang ekstrem                        (opsional)
ROLL_EXTREME = 18.0     # miring ekstrem                        (opsional)


def _beep(notes: list[tuple[int, int]]) -> None:
    """Suara di thread terpisah (winsound stdlib Windows; diam di OS lain)."""
    import threading

    def run() -> None:
        try:
            import winsound
            for freq, ms in notes:
                winsound.Beep(freq, ms)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=run, daemon=True).start()


SND_OK = [(880, 120), (1318, 180)]        # ding naik: foto tersimpan
SND_NEXT = [(1174, 150)]                  # tone tunggal: lanjut pose
SND_REJECT = [(330, 220)]                 # tone rendah: ditolak, ulangi
SND_SKIP = [(660, 100)]                   # tone tipis: pose opsional dilewati
SND_DONE = [(880, 120), (1174, 120), (1567, 250)]  # fanfare: semua selesai


@dataclass
class Metrics:
    roll: float
    face_w: float
    bright: float


# --------------------------------------------------------------- daftar pose ---
# tiap pose: (judul, instruksi, kondisi(m, ctx) -> bool, set_baseline?, wajib?)
def _tilt(m: Metrics, ctx: dict) -> bool:
    return abs(m.roll) > ROLL_TILT and ctx.get("tilt_sign") != (1 if m.roll > 0 else -1)


def _tilt_opp(m: Metrics, ctx: dict) -> bool:
    return abs(m.roll) > ROLL_TILT and ctx.get("tilt_sign") is not None \
        and (1 if m.roll > 0 else -1) != ctx["tilt_sign"]


POSES_ENROLL = [
    ("POSE 1/5: TEGAK", "hadap kamera lurus, kepala tegak",
     lambda m, c: abs(m.roll) < ROLL_STRAIGHT, True, True),
    ("POSE 2/5: CONDONGKAN KEPALA", "condongkan kepala ke bahu (kiri/kanan bebas)",
     _tilt, False, True),
    ("POSE 3/5: CONDONG SISI LAIN", "condongkan kepala ke bahu sebelahnya",
     _tilt_opp, False, True),
    ("POSE 4/5: MUNDUR", "mundur satu langkah (wajah jadi kecil)",
     lambda m, c: m.face_w < W_BACK * c.get("base_w", 1e9), False, True),
    ("POSE 5/5: MAJU DEKAT", "dekatkan wajah ke kamera (~40-50 cm)",
     lambda m, c: m.face_w > W_NEAR * c.get("base_w", 0), False, True),
    # --- opsional (cahaya): lewati bila lingkungan tak memungkinkan ---
    ("OPS 6/8: CAHAYA TERANG", "arahkan cahaya terang ke depan wajah",
     lambda m, c: m.bright > B_BRIGHT * c.get("base_bright", 1e9), False, False),
    ("OPS 7/8: CAHAYA SAMPING", "pindahkan sumber cahaya ke samping wajah",
     lambda m, c: True, False, False),
    ("OPS 8/8: REMANG", "redupkan lampu separuh",
     lambda m, c: m.bright < B_DIM * c.get("base_bright", 1e9), False, False),
]

POSES_EVAL_EXTRA = [
    # --- opsional (stress): jadwalkan saat sesi malam bila memungkinkan ---
    ("OPS 6/7: REMANG EKSTREM", "redupkan lampu lagi (sangat remang)",
     lambda m, c: m.bright < B_DIM_HARD * c.get("base_bright", 1e9), False, False),
    ("OPS 7/7: MIRING EKSTREM", "condongkan kepala lebih ekstrem",
     lambda m, c: abs(m.roll) > ROLL_EXTREME, False, False),
]

SPOOF_HINTS = [
    "pegang foto/layar: JARAK SEDANG",
    "pegang foto/layar: LEBIH DEKAT",
    "pegang foto/layar: LEBIH JAUH",
    "pegang foto/layar: MIRINGKAN sedikit",
]


def out_dir_for(args) -> Path:
    if args.mode == "spoof":
        return PROJECT_ROOT / "data" / "spoof" / args.attack / args.subject
    return PROJECT_ROOT / "data" / "raw" / args.subject / args.session


def poses_for(args) -> list:
    if args.mode == "spoof":
        return []
    if args.mode == "enroll":
        return POSES_ENROLL
    return POSES_ENROLL + POSES_EVAL_EXTRA  # eval (7: 5 wajib + 2 opsional)


def next_index(out_dir: Path, prefix: str) -> int:
    n = 0
    for p in out_dir.glob(f"{prefix}_*.jpg"):
        try:
            n = max(n, int(p.stem.split("_")[-1]))
        except ValueError:
            continue
    return n + 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Guided auto-capture per pose")
    ap.add_argument("--mode", choices=["enroll", "eval", "spoof"], required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--session", default="s1", help="s1|s2|s3 (mode enroll/eval)")
    ap.add_argument("--attack", choices=["print", "screen"], default="print")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    from capture_webcam import start_camera  # reuse loader yang sudah tahan banting

    if args.list:
        cap, found, size = start_camera(0)
        if cap is not None:
            ok, frame = cap.read()
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if ok else None
            print(f"camera[{found}]: {frame.shape[1]}x{frame.shape[0]} "
                  f"mean={g.mean():.0f}" if ok else f"camera[{found}]: tanpa frame")
            cap.release()
        return 0 if cap is not None else 1

    out_dir = out_dir_for(args)
    out_dir.mkdir(parents=True, exist_ok=True)
    poses = poses_for(args)
    n_req = sum(1 for p in poses if p[4])
    n_opt = len(poses) - n_req
    prefix = "img"
    idx0 = next_index(out_dir, prefix)
    print(f"Mode={args.mode} subjek={args.subject} -> {out_dir}")
    print(f"Target: {n_req} pose WAJIB + {n_opt} opsional (mulai img_{idx0:03d})")

    pipe = VerifyPipeline(load_config())
    skip_antispoof = args.mode == "spoof"  # label spoof diharapkan pada data serangan

    cap, actual, size = start_camera(args.camera)
    if cap is None:
        print("GAGAL: tidak ada kamera yang bisa dibuka")
        return 1
    print(f"Kamera {actual} @ {size}. SPACE=jepret manual  s=lewati(opsional)  q=keluar")

    ctx: dict = {"tilt_sign": None, "base_w": None, "base_bright": None}
    pose_i = 0
    streak = 0
    saved = 0
    req_done = 0
    skipped: list[str] = []
    last_shot = 0.0
    flash_until = 0.0

    while pose_i < len(poses):
        try:
            ok, frame = cap.read()
        except cv2.error:
            cap.release()
            cap, actual, size = start_camera(actual)
            if cap is None:
                print("GAGAL: kamera mati")
                break
            continue
        if not ok or frame is None:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        bright = float(gray.mean())
        face = pipe.engine.get_primary_face(frame)

        m = Metrics(roll=0.0, face_w=0.0, bright=bright)
        face_ok = False
        if face is not None:
            x1, y1, x2, y2 = face.bbox
            m.face_w = float(x2 - x1)
            pose = getattr(face, "pose", None)
            if pose is not None:
                m.roll = float(pose[2])
            face_ok = True

        if pose_i < len(poses):
            title, instr, cond, set_baseline, required = poses[pose_i]
        else:  # mode spoof: hint bergilir, tanpa kondisi pose
            title = f"SPOOF {saved + 1}/10: {SPOOF_HINTS[saved % len(SPOOF_HINTS)]}"
            instr = "layar/foto wajah menghadap kamera"
            cond = lambda m, c: True  # noqa: E731
            set_baseline = required = False

        # baseline diambil dari pose pertama (tegak)
        if pose_i == 0 and face_ok:
            ctx["base_w"] = m.face_w if ctx.get("base_w") is None else \
                0.9 * ctx["base_w"] + 0.1 * m.face_w
            ctx["base_bright"] = bright if ctx.get("base_bright") is None else \
                0.9 * ctx["base_bright"] + 0.1 * bright

        in_pose = face_ok and cond(m, ctx)
        streak = streak + 1 if in_pose else 0
        ready = in_pose and streak >= STREAK_NEEDED and (time.time() - last_shot) > COOLDOWN_S

        if ready:
            # gate penuh sebelum menyimpan
            if skip_antispoof:
                from presensi.quality.quality import check_frame
                g_ok, g_reason = check_frame(frame, pipe.cfg["quality"])
                if not g_ok or not face_ok or m.face_w < pipe.cfg["quality"]["face_min_px"]:
                    g_reason = g_reason or ("face_too_small" if face_ok else "no_face")
                    rejected = g_reason
                else:
                    rejected = None
            else:
                _emb, rejected = pipe.embed_image(frame)

            if rejected is None:
                idx0 = next_index(out_dir, prefix)
                p = out_dir / f"{prefix}_{idx0:03d}.jpg"
                cv2.imwrite(str(p), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                saved += 1
                if required:
                    req_done += 1
                last_shot = time.time()
                streak = 0
                if set_baseline or pose_i == 0:
                    ctx["base_w"] = m.face_w
                    ctx["base_bright"] = bright
                if pose_i == 1 or (pose_i == 2 and ctx.get("tilt_sign") is None):
                    ctx["tilt_sign"] = 1 if m.roll > 0 else -1
                pose_i += 1
                flash_until = time.time() + 1.2
                _beep(SND_OK + SND_NEXT if pose_i < len(poses) else SND_DONE)
                print(f"  [OK] {p.name}  (roll={m.roll:.0f} w={m.face_w:.0f} bright={bright:.0f})"
                      + ("" if pose_i < len(poses) else "  << SEMUA POSE SELESAI"))
            else:
                streak = 0
                _beep(SND_REJECT)
                print(f"  [DITOLAK] {rejected} — pose diulang otomatis")

        # ---------------- tampilan panduan ----------------
        disp = frame.copy()
        h, w_ = disp.shape[:2]
        if face_ok:
            x1, y1, x2, y2 = (int(v) for v in face.bbox)
            color = (0, 200, 0) if in_pose else (0, 165, 255)
            cv2.rectangle(disp, (x1, y1), (x2, y2), color, 2)
        cv2.rectangle(disp, (0, 0), (w_, 110), (30, 30, 30), -1)
        cv2.putText(disp, title, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (0, 255, 255), 2)
        cv2.putText(disp, instr + ("   [s=lewati]" if not required else ""),
                    (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        state = f"TAHAN... {streak}/{STREAK_NEEDED}" if in_pose else "ikuti arahan di atas"
        cv2.putText(disp, f"{state}   bright={bright:.0f} w={m.face_w:.0f} roll={m.roll:.0f}",
                    (10, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                    (0, 255, 0) if in_pose else (200, 200, 200), 2)
        cv2.putText(disp, f"tersimpan {saved}  |  wajib {req_done}/{n_req}",
                    (10, h - 55), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        if time.time() < flash_until:  # banner hijau sesaat setelah jepret sukses
            cv2.rectangle(disp, (0, h // 2 - 50), (w_, h // 2 + 50), (0, 160, 0), -1)
            cv2.putText(disp, "BERHASIL! POSE SELANJUTNYA...", (40, h // 2 + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3)
        cv2.imshow("guided_capture", disp)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("s") and not required:
            skipped.append(title)
            pose_i += 1
            streak = 0
            _beep(SND_SKIP)
            print(f"  [LEWATI] {title}")
            if pose_i >= len(poses):
                _beep(SND_DONE)
        elif key == ord(" "):  # jepret manual darurat (masih lewat gate)
            if skip_antispoof:
                g_ok = face_ok and m.face_w >= pipe.cfg["quality"]["face_min_px"]
                g_gate = None if g_ok else "gate"
            else:
                g_gate = pipe.embed_image(frame)[1]
            if face_ok and g_gate is None:
                idx0 = next_index(out_dir, prefix)
                cv2.imwrite(str(out_dir / f"{prefix}_{idx0:03d}.jpg"), frame,
                            [cv2.IMWRITE_JPEG_QUALITY, 95])
                saved += 1
                if required:
                    req_done += 1
                pose_i += 1
                streak = 0
                flash_until = time.time() + 1.2
                _beep(SND_OK + SND_NEXT if pose_i < len(poses) else SND_DONE)
                print(f"  [MANUAL] tersimpan ({saved} total)")
            else:
                _beep(SND_REJECT)
                print("  [MANUAL DITOLAK] gate tidak lolos")

    cap.release()
    cv2.destroyAllWindows()
    if skipped:
        print(f"Pose dilewati ({len(skipped)}): {', '.join(skipped)}")
    selesai = req_done >= n_req
    print(f"Selesai: {saved} foto ({req_done}/{n_req} wajib) -> {out_dir}")
    print(f"Validasi akhir: uv run python scripts/collect_data.py --check {out_dir}")
    return 0 if selesai else 1


if __name__ == "__main__":
    raise SystemExit(main())
