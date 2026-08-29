"""Jalankan API server: python scripts/run_api.py

Host/port dari config.yaml api.* (override env PRES_HOST / PRES_PORT).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import uvicorn  # noqa: E402

from presensi.pipeline.verify import load_config  # noqa: E402


def main() -> None:
    cfg = load_config()["api"]
    uvicorn.run("presensi.api.app:app",
                host=os.environ.get("PRES_HOST", cfg["host"]),
                port=int(os.environ.get("PRES_PORT", cfg["port"])),
                log_level="info")


if __name__ == "__main__":
    main()
