"""Liveness aktif (challenge-response): kedip + senyum via geometri landmark.

Lapisan ke-2 anti-spoofing selain MiniFASNet pasif (antispoof.py). Prinsip:
foto cetak & layar statis TIDAK bisa berkedip/senyum mengikuti perintah.

Metrik (dari ring landmark 106-titik insightface, dipetakan EMPIRIS lewat
5 jangkar kps + validasi 17 gambar — lihat scripts/probe_landmarks.py):
  LEFT_EYE  = 33..42, RIGHT_EYE = 87..96  -> EAR = tinggi/lebar ring
  MOUTH     = 52..71 (sudut = titik x ekstrem) -> lebar mulut + angkat sudut

Desain: BASELINE PERSONAL (netral di awal sesi) — ambang relatif terhadap
wajah subjek sendiri, bukan angka global (geometri mata/mulut bervariasi
antar orang). State machine per-frame; CLI kamera di scripts/verify_liveness.py.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np

LEFT_EYE = list(range(33, 43))    # 10 titik
RIGHT_EYE = list(range(87, 97))   # 10 titik
MOUTH = list(range(52, 72))       # 20 titik; sudut = x ekstrem


def ear(lm: np.ndarray, ring: list[int]) -> float:
    """Eye Aspect Ratio (surrogate 10-titik): tinggi vertikal / lebar horizontal."""
    pts = lm[ring]
    h = float(pts[:, 1].max() - pts[:, 1].min())
    w = float(pts[:, 0].max() - pts[:, 0].min())
    return h / max(w, 1e-6)


def mouth_metrics(lm: np.ndarray) -> tuple[float, float]:
    """Return (width, lift) mulut. lift = kenaikan sudut relatif thd pusat bibir,
    dinormalisasi lebar (dimensionless). Senyum = width naik + lift naik."""
    pts = lm[MOUTH]
    i_l = int(np.argmin(pts[:, 0]))
    i_r = int(np.argmax(pts[:, 0]))
    width = float(pts[i_r, 0] - pts[i_l, 0])
    center_y = float(np.median(pts[:, 1]))
    corner_y = float((pts[i_l, 1] + pts[i_r, 1]) / 2.0)
    lift = (center_y - corner_y) / max(width, 1e-6)
    return width, lift


@dataclass
class LivenessConfig:
    baseline_frames: int = 25      # frame netral utk baseline (±1.5 dtk)
    blink_timeout_s: float = 8.0
    smile_timeout_s: float = 8.0
    ear_close_ratio: float = 0.60  # EAR < 60% baseline = tertutup
    ear_open_ratio: float = 0.80   # kembali > 80% = terbuka (siklus selesai)
    smile_width_ratio: float = 1.12
    smile_lift_delta: float = 0.04   # kenaikan lift vs baseline (relatif personal)
    stable_frames: int = 5
    random_order: bool = True


class LivenessSession:
    """State machine liveness per-frame. `update(lm)` dipanggil tiap frame kamera.

    Fase: baseline -> blink -> smile -> done (urutan blink/smile bisa diacak).
    update() return dict: {phase, progress, message, done, failed, reason}.
    """

    BASELINE, BLINK, SMILE, DONE, FAIL = ("baseline", "blink", "smile", "done", "fail")

    def __init__(self, cfg: LivenessConfig | None = None):
        self.cfg = cfg or LivenessConfig()
        self._phases = [self.BLINK, self.SMILE]
        if self.cfg.random_order and np.random.default_rng().random() < 0.5:
            self._phases.reverse()
        self.phase = self.BASELINE
        self.progress = 0.0
        self.message = "hadap kamera, ekspresi netral"
        self.done = False
        self.failed = False
        self.reason: str | None = None

        self._base_buf: deque = deque(maxlen=self.cfg.baseline_frames)
        self._base_ear = self._base_w = self._base_lift = None
        self._phase_t0: float | None = None
        self._blink_armed = False       # sudah melihat mata terbuka?
        self._blink_closed = False      # sudah melihat mata tertutup?
        self._smile_streak = 0
        self._fails: list[str] = []

    # ------------------------------------------------------------------ #
    def update(self, lm: np.ndarray | None, now: float) -> dict:
        if self.done:
            return self._state()
        if lm is None:
            self.message = "wajah tidak terdeteksi"
            # timeout tetap berjalan di fase challenge
            if self.phase in (self.BLINK, self.SMILE):
                self._check_timeout(now)
            return self._state()

        e_l, e_r = ear(lm, LEFT_EYE), ear(lm, RIGHT_EYE)
        e = min(e_l, e_r)  # mata "tertutup" bila SALAH SATU menutup
        width, lift = mouth_metrics(lm)

        if self.phase == self.BASELINE:
            self._base_buf.append((e, width, lift))
            self.progress = len(self._base_buf) / self.cfg.baseline_frames
            self.message = f"tetap netral... {len(self._base_buf)}/{self.cfg.baseline_frames}"
            if len(self._base_buf) >= self.cfg.baseline_frames:
                arr = np.asarray(self._base_buf)
                self._base_ear, self._base_w, self._base_lift = arr.mean(axis=0)
                self.phase = self._phases.pop(0)
                self._phase_t0 = now
                self.message = ("KEDIP sekali!" if self.phase == self.BLINK
                                else "SENYUM lebar!")
            return self._state()

        if self.phase == self.BLINK:
            base = max(self._base_ear, 1e-3)
            if e > self.cfg.ear_open_ratio * base:
                self._blink_armed = True
            if self._blink_armed and e < self.cfg.ear_close_ratio * base:
                self._blink_closed = True
                self.message = "kedipan terlihat, buka lagi..."
            if self._blink_closed and e > self.cfg.ear_open_ratio * base:
                self._advance(now, "KEDIP terverifikasi")
            else:
                self.message = "KEDIP sekali!" if not self._blink_closed else self.message
                self._check_timeout(now)
            return self._state()

        if self.phase == self.SMILE:
            smiling = (width >= self.cfg.smile_width_ratio * self._base_w
                       and lift >= self._base_lift + self.cfg.smile_lift_delta)
            self._smile_streak = self._smile_streak + 1 if smiling else 0
            self.message = ("SENYUM terverifikasi!" if smiling
                            else "SENYUM lebar! (lebar + angkat sudut mulut)")
            if self._smile_streak >= self.cfg.stable_frames:
                self._advance(now, "SENYUM terverifikasi")
            else:
                self._check_timeout(now)
            return self._state()

        return self._state()

    # ------------------------------------------------------------------ #
    def _advance(self, now: float, msg: str) -> None:
        if self._phases:
            self.phase = self._phases.pop(0)
            self._phase_t0 = now
            self._blink_armed = self._blink_closed = False
            self._smile_streak = 0
            self.message = "KEDIP sekali!" if self.phase == self.BLINK else "SENYUM lebar!"
        else:
            self.phase = self.DONE
            self.done = True
            self.progress = 1.0
            self.message = f"LIVENESS OK ({msg.lower()})"

    def _check_timeout(self, now: float) -> None:
        if self._phase_t0 is None:
            self._phase_t0 = now
            return
        limit = (self.cfg.blink_timeout_s if self.phase == self.BLINK
                 else self.cfg.smile_timeout_s)
        if now - self._phase_t0 > limit:
            self.phase = self.FAIL
            self.failed = True
            self.reason = f"timeout fase {self.phase}"
            self.message = "challenge gagal — ulangi"

    def _state(self) -> dict:
        return {"phase": self.phase, "progress": self.progress,
                "message": self.message, "done": self.done,
                "failed": self.failed, "reason": self.reason}
