"""Unduh model buffalo_l (SCRFD + ArcFace) ke models/ via insightface model zoo.

Pemakaian: python scripts/download_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

MODELS_DIR = PROJECT_ROOT / "models"


def main() -> int:
    # insightface me-render zip ke <root>/models/buffalo_l.zip lalu ekstrak;
    # root kita = PROJECT_ROOT sehingga model berakhir di PROJECT_ROOT/models/buffalo_l
    from insightface.app import FaceAnalysis

    MODELS_DIR.mkdir(exist_ok=True)
    print("Mengunduh buffalo_l dari insightface model zoo ...")
    app = FaceAnalysis(name="buffalo_l", root=str(PROJECT_ROOT),
                       providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=-1, det_size=(640, 640))
    onnx_files = sorted((MODELS_DIR / "buffalo_l").glob("*.onnx"))
    print("Model siap:")
    for f in onnx_files:
        print(f"  - {f.name}  ({f.stat().st_size / 1e6:.1f} MB)")
    return 0 if onnx_files else 1


if __name__ == "__main__":
    raise SystemExit(main())
