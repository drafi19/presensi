"""Anti-spoofing MiniFASNet — ensemble V2 (crop 2.7x) + V1SE (full frame).

Referensi: third_party/Silent-Face-Anti-Spoofing (minivision-ai, MIT License).
Detail inferensi diikuti PERSIS dari referensi (test.py + generate_patches.py):
  - input BGR 0-255 float, TANPA /255 dan TANPA normalisasi (to_tensor "modify by zkx")
  - label 1 = real (test.py: label = argmax(prediction); label == 1 -> real)
  - V2   : crop bbox discale 2.7x (dibatasi tepi frame) -> resize 80x80
  - V1SE : full frame langsung resize 80x80 (crop=False)
  - conv6 kernel = ((h+15)//16, (w+15)//16) = (5,5) untuk input 80x80
  - skor ensemble = jumlah softmax kedua model (test.py: sum(prediction_list))
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

# --- import definisi model dari third_party (namespace package, tanpa di-copy) ---
_SFAS_ROOT = Path(__file__).resolve().parents[3] / "third_party" / "Silent-Face-Anti-Spoofing"
if str(_SFAS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SFAS_ROOT))

import torch  # noqa: E402
import torch.nn.functional as tnf  # noqa: E402
from src.model_lib.MiniFASNet import MiniFASNetV1SE, MiniFASNetV2  # noqa: E402

# (nama file model, scale crop; None = full frame) — plan resmi dari test.py referensi
DEFAULT_MODEL_PLAN = [
    ("2.7_80x80_MiniFASNetV2.pth", 2.7),
    ("4_0_0_80x80_MiniFASNetV1SE.pth", None),
]
_INPUT_SIZE = 80


def _get_new_box(src_w: int, src_h: int, bbox: tuple[int, int, int, int], scale: float):
    """Salinan persis CropImage._get_new_box dari generate_patches.py referensi."""
    x, y, box_w, box_h = bbox
    scale = min((src_h - 1) / box_h, min((src_w - 1) / box_w, scale))
    new_width = box_w * scale
    new_height = box_h * scale
    center_x, center_y = box_w / 2 + x, box_h / 2 + y
    left_top_x = center_x - new_width / 2
    left_top_y = center_y - new_height / 2
    right_bottom_x = center_x + new_width / 2
    right_bottom_y = center_y + new_height / 2
    if left_top_x < 0:
        right_bottom_x -= left_top_x
        left_top_x = 0
    if left_top_y < 0:
        right_bottom_y -= left_top_y
        left_top_y = 0
    if right_bottom_x > src_w - 1:
        left_top_x -= right_bottom_x - src_w + 1
        right_bottom_x = src_w - 1
    if right_bottom_y > src_h - 1:
        left_top_y -= right_bottom_y - src_h + 1
        right_bottom_y = src_h - 1
    return int(left_top_x), int(left_top_y), int(right_bottom_x), int(right_bottom_y)


class AntiSpoof:
    """Ensemble MiniFASNet. predict() -> (label, p_real); label 1 = real."""

    def __init__(self, model_dir: Path, device: str = "cpu",
                 model_plan: list[tuple[str, float | None]] | None = None):
        self.device = torch.device(device)
        self.model_dir = Path(model_dir)
        if not self.model_dir.exists():
            raise FileNotFoundError(
                f"Model anti-spoof tidak ditemukan di {self.model_dir} — "
                f"lihat third_party/Silent-Face-Anti-Spoofing/resources/anti_spoof_models")
        self.models: list[tuple[torch.nn.Module, float | None]] = []
        for name, scale in (model_plan or DEFAULT_MODEL_PLAN):
            self.models.append((self._load(self.model_dir / name), scale))

    def _load(self, path: Path) -> torch.nn.Module:
        # nama file mengkodekan arsitektur (konvensi repo referensi)
        model_cls = MiniFASNetV2 if "MiniFASNetV2" in path.name else MiniFASNetV1SE
        kernel = ((_INPUT_SIZE + 15) // 16, (_INPUT_SIZE + 15) // 16)
        model = model_cls(conv6_kernel=kernel)
        state = torch.load(path, map_location=self.device, weights_only=True)
        if any(k.startswith("module.") for k in state):  # checkpoint DataParallel
            state = {k[7:]: v for k, v in state.items()}
        model.load_state_dict(state)
        return model.to(self.device).eval()

    def _make_patch(self, img_bgr: np.ndarray, bbox, scale: float | None) -> np.ndarray:
        if scale is None:  # full frame
            return cv2.resize(img_bgr, (_INPUT_SIZE, _INPUT_SIZE))
        h, w = img_bgr.shape[:2]
        x0, y0, x1, y1 = _get_new_box(w, h, bbox, scale)
        crop = img_bgr[y0:y1 + 1, x0:x1 + 1]
        return cv2.resize(crop, (_INPUT_SIZE, _INPUT_SIZE))

    @torch.no_grad()
    def predict(self, img_bgr: np.ndarray, bbox: tuple[int, int, int, int]) -> tuple[int, float]:
        """Return (label, p_real): label 1 = real (aturan resmi referensi).

        p_real = massa probabilitas kelas real pada jumlah softmax ensemble
        (dipakai sebagai confidence; verdict utama dari label argmax).
        """
        total = np.zeros(3, dtype=np.float64)
        for model, scale in self.models:
            patch = self._make_patch(img_bgr, bbox, scale)
            x = torch.from_numpy(patch.transpose(2, 0, 1)).float().unsqueeze(0).to(self.device)
            probs = tnf.softmax(model(x), dim=1).cpu().numpy()[0]
            total += probs
        label = int(np.argmax(total))
        return label, float(total[1])
