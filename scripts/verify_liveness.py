"""Verifikasi wajah + liveness aktif (kedip & senyum) dari kamera.

Alur: baseline netral -> challenge kedip -> challenge senyum (urutan acak)
-> batch frame terakhir diverifikasi penuh oleh pipeline (anti-spoof pasif
MiniFASNet tetap jalan sebagai lapisan kedua).

Pemakaian:
  uv run python scripts/verify_liveness.py --user amin
  uv run python scripts/verify_liveness.py            # mode 1:N
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from pathlib import Path

import cv2
import numpy as np

try:
    cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_ERROR)
except Exception:  # noqa: BLE001
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from presensi.pipeline.liveness import LivenessSession  # noqa: E402
from presensi.pipeline.verify import VerifyPipeline, load_config  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Verifikasi + liveness aktif")
    ap.add_argument("--user", default=None, help="klaim user (1:1); tanpa ini = 1:N")
    ap.add_argument("--camera", type=int, default=0)
    args = ap.parse_args()

    pipe = VerifyPipeline(load_config())
    sess = LivenessSession()
    from capture_webcam import start_camera
    cap, cam, _size = start_camera(args.camera)
    if cap is None:
        print("GAGAL: kamera tidak ada")
        return 1

    recent: deque = deque(maxlen=12)  # frame valid terakhir utk verify
    win = "verify_liveness"
    print(f"Mode: {'1:1 (' + args.user + ')' if args.user else '1:N'}")
    while not sess.done and not sess.failed:
        ok, frame = cap.read()
        if not ok:
            continue
        face = pipe.engine.get_primary_face(frame)
        lm = None
        if face is not None and face.landmark_2d_106 is not None:
            lm = np.asarray(face.landmark_2d_106, dtype=np.float64)
            recent.append(frame)

        st = sess.update(lm, time.time())

        disp = frame.copy()
        h, w = disp.shape[:2]
        cv2.rectangle(disp, (0, 0), (w, 110), (30, 30, 30), -1)
        cv2.putText(disp, st["message"], (10, 45), cv2.FONT_HERSHEY_SIMPLEX,
                    0.9, (0, 255, 255), 2)
        cv2.putText(disp, f"fase: {st['phase']}", (10, 85),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        bar = int(w * min(1.0, max(0.0, st["progress"])))
        cv2.rectangle(disp, (0, h - 12), (bar, h), (0, 200, 0), -1)
        if face is not None:
            x1, y1, x2, y2 = (int(v) for v in face.bbox)
            cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 200, 0) if lm is not None else (0, 0, 255), 2)
        cv2.imshow(win, disp)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            cap.release(); cv2.destroyAllWindows()
            print("DIBATALKAN user")
            return 1

    cap.release()
    cv2.destroyAllWindows()

    if sess.failed:
        print(json.dumps({"status": "liveness_fail", "reason": sess.reason},
                         ensure_ascii=False))
        return 1

    # ---- liveness lolos -> verify penuh pada frame terkini ----
    frames = list(recent)
    if len(frames) < 3:
        print("Frame valid terlalu sedikit saat verify")
        return 1
    verdict, _ = pipe.verify_batch(frames, claimed_user=args.user)
    print(json.dumps({"liveness": "pass", **verdict}, ensure_ascii=False))
    return 0 if verdict["status"] == "match" else 1


if __name__ == "__main__":
    raise SystemExit(main())
