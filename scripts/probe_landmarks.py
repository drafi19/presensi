"""Probe landmark: identifikasi indeks mata & mulut secara EMPIRIS.

Alur (ikuti instruksi di jendela kamera):
  5 dtk netral -> 8 dtk KEDIP berkali-kali -> 8 dtk SENYUM-lebar tahan -> 4 dtk netral

Analisis: indeks dgn pergeseran VERTIKAL terbesar saat kedip = mata;
HORIZONTAL terbesar saat senyum = sudut mulut.

Pemakaian: uv run python scripts/probe_landmarks.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from presensi.pipeline.verify import VerifyPipeline, load_config  # noqa: E402

PHASES = [("NETRAL (diam)", 5), ("KEDIP berkali-kali!", 8),
          ("SENYUM lebar, tahan!", 8), ("NETRAL (diam)", 4)]


def main() -> int:
    from capture_webcam import start_camera
    pipe = VerifyPipeline(load_config())
    cap, cam, _size = start_camera(0)
    if cap is None:
        print("GAGAL: kamera tidak ada")
        return 1

    series: dict[str, list[np.ndarray]] = {}
    win = "probe_landmarks"
    for phase, dur in PHASES:
        t0 = time.time()
        frames: list[np.ndarray] = []
        while time.time() - t0 < dur:
            ok, frame = cap.read()
            if not ok:
                continue
            face = pipe.engine.get_primary_face(frame)
            disp = frame.copy()
            cv2.putText(disp, f"{phase}  ({dur - (time.time()-t0):.0f}s)",
                        (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 255, 255), 2)
            if face is not None and face.landmark_2d_106 is not None:
                frames.append(np.asarray(face.landmark_2d_106, dtype=np.float32))
                x1, y1, x2, y2 = (int(v) for v in face.bbox)
                cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 200, 0), 2)
            else:
                cv2.putText(disp, "wajah tidak terdeteksi!", (10, 80),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            cv2.imshow(win, disp)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                cap.release(); cv2.destroyAllWindows(); return 1
        series[phase] = frames
        print(f"  [{phase}] {len(frames)} frame landmark")
    cap.release()
    cv2.destroyAllWindows()

    def stack(key: str) -> np.ndarray | None:
        return np.stack(series[key]) if series[key] else None

    neutral1, blink, smile, neutral2 = (stack(k) for k in
                                        ("NETRAL (diam)", "KEDIP berkali-kali!",
                                         "SENYUM lebar, tahan!", "NETRAL (diam)"))
    n_min = min(len(neutral1), len(neutral2))
    if n_min < 3 or blink is None or smile is None:
        print("Data kurang — ulangi, pastikan wajah terdeteksi sepanjang fase.")
        return 1

    # kedip: |dy| per indeks (netral gabungan vs fase kedip)
    n_ref = np.concatenate([neutral1, neutral2])[:, :, 1]
    dy = np.abs(blink[:, :, 1].mean(axis=0) - n_ref.mean(axis=0))
    eye_idx = np.argsort(dy)[::-1][:10]
    # senyum: |dx| per indeks
    dx = np.abs(smile[:, :, 0].mean(axis=0) - n_ref[:, :].mean(axis=0)
                if n_ref.shape[0] else 0)
    dx = np.abs(smile[:, :, 0].mean(axis=0) - np.concatenate([neutral1, neutral2])[:, :, 0].mean(axis=0))
    mouth_idx = np.argsort(dx)[::-1][:10]

    print("\n== Kandidat MATA (dy terbesar saat kedip) ==")
    for i in eye_idx:
        print(f"  idx {i:3d}  dy={dy[i]:.2f}px")
    print("== Kandidat MULUT (dx terbesar saat senyum) ==")
    for i in mouth_idx:
        print(f"  idx {i:3d}  dx={dx[i]:.2f}px")

    out = PROJECT_ROOT / "data" / "probe_landmarks.npz"
    np.savez(out, **{k: np.array(v, dtype=object) for k, v in series.items()})
    print(f"\nSeri mentah tersimpan: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
