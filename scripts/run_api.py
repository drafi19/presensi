"""Jalankan API server: python scripts/run_api.py

Host/port dari config.yaml api.* (override env PRES_HOST / PRES_PORT).
HTTPS opsional: bila certs/cert.pem + certs/key.pem ada (env PRES_SSL=1),
server jalan di https:// — WAJIB utk akses kamera browser dari perangkat lain
(browser memblokir getUserMedia di http non-localhost). Sertifikat self-signed:
browser akan minta konfirmasi "lanjutkan" sekali.

Contoh:
  python scripts/run_api.py                 # http
  PRES_SSL=1 python scripts/run_api.py      # https (pakai certs/)
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
    ssl_certfile = PROJECT_ROOT / "certs" / "cert.pem"
    ssl_keyfile = PROJECT_ROOT / "certs" / "key.pem"
    use_ssl = os.environ.get("PRES_SSL") == "1" and ssl_certfile.exists() and ssl_keyfile.exists()

    kwargs = dict(
        app="presensi.api.app:app",
        host=os.environ.get("PRES_HOST", cfg["host"]),
        port=int(os.environ.get("PRES_PORT", cfg["port"])),
        log_level="info",
    )
    if use_ssl:
        kwargs.update(ssl_certfile=str(ssl_certfile), ssl_keyfile=str(ssl_keyfile))
    uvicorn.run(**kwargs)


if __name__ == "__main__":
    main()
