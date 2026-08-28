"""Setup model untuk fresh clone:
1. Unduh 2 bobot MiniFASNet (.pth) dari repo upstream Silent-Face-Anti-Spoofing
   (tidak ikut commit karena *.pth di-gitignore).
2. buffalo_l diunduh terpisah: python scripts/download_models.py

Pemakaian: python scripts/fetch_antispoof_weights.py
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

BASE = "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/resources/anti_spoof_models"
FILES = [
    "2.7_80x80_MiniFASNetV2.pth",
    "4_0_0_80x80_MiniFASNetV1SE.pth",
]
DEST = PROJECT_ROOT / "third_party" / "Silent-Face-Anti-Spoofing" / "resources" / "anti_spoof_models"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    rc = 0
    for name in FILES:
        dest = DEST / name
        if dest.exists() and dest.stat().st_size > 1e6:
            print(f"OK (sudah ada): {name}")
            continue
        url = f"{BASE}/{name}"
        print(f"Mengunduh {url} ...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
                f.write(resp.read())
            print(f"  -> {dest} ({dest.stat().st_size / 1e6:.2f} MB)")
        except Exception as e:  # noqa: BLE001
            print(f"  GAGAL: {e}")
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
