# Presensi — Face Recognition Attendance System

Sistem presensi dengan verifikasi wajah: user presensi dari app mobile,
server AI memverifikasi wajah (dengan anti-spoofing) dan mencatat hasilnya
di audit log server.

**Status: tahap perancangan & pembagian kerja. Implementasi dikerjakan per
divisi di branch masing-masing; branch `main` adalah kerangka bersama.**

| Branch | Isi |
|--------|-----|
| [`main`](https://github.com/drafi19/presensi) | kerangka monorepo + dokumen desain (halaman ini) |
| [`ai`](https://github.com/drafi19/presensi/tree/ai) | pengerjaan penuh bagian AI (pipeline, API, evaluasi) |
| `mobile` | (Raihan) aplikasi mobile |

## Struktur

```
presensi/
├── ai/                  bagian AI  (dikerjakan di branch ai)
│   ├── models/
│   ├── inference/
│   └── README.md
├── mobile/              bagian mobile (Raihan)
│   ├── lib/
│   ├── assets/
│   └── README.md
├── src/presensi/        backend/API/core (diisi saat integrasi)
├── docs/                dokumen desain — milik bersama
├── third_party/         pustaka pihak ketiga + lisensi
└── README.md
```

## Dokumen utama

- [docs/DESAIN.md](docs/DESAIN.md) — desain teknis end-to-end (arsitektur,
  keputusan teknis + alternatifnya, pipeline, evaluasi, roadmap)
- [docs/API.md](docs/API.md) — kontrak API v1 untuk mobile client
- [docs/PENGUMPULAN_DATA.md](docs/PENGUMPULAN_DATA.md) — protokol pengumpulan
  data & evaluasi (FAR/FRR, anti-spoof)

## Alur sistem (ringkas)

1. User login di app (akun mengikat HP ke `user_id`)
2. App memvalidasi user di area kerja (GPS/geofence — sisi mobile)
3. App merekam ±2 detik → mengirim batch frame JPEG + `user_id` ke API
4. Server: deteksi wajah → anti-spoofing → embedding → matching → verdict
   `match / no_match / spoof / no_face / low_quality`
5. Server menulis audit log; record presensi resmi diturunkan dari log server

## Tim

- [@drafi19](https://github.com/drafi19) — AI/ML
- Raihan — Mobile development
