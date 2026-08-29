# `ai/` — Komponen AI (face recognition)

> **Status: pengerjaan penuh ada di branch [`ai`](https://github.com/drafi19/presensi/tree/ai).**
> Branch `main` sengaja TIDAK berisi implementasi AI — struktur di main adalah
> kerangka kerja bersama yang disepakati tim.

Rencana isi folder ini (dikerjakan di branch `ai`, masuk main saat beres):

```
ai/
├── models/      bobot & definisi model (buffalo_l, MiniFASNet)
└── inference/   kode inferensi: deteksi -> anti-spoof -> embedding -> matching
```

## Cakupan bagian AI

- Pipeline verifikasi wajah (SCRFD → MiniFASNet → ArcFace → cosine + voting)
- Anti-spoofing (ensemble MiniFASNet)
- API server (FastAPI) + audit log
- Evaluasi FAR/FRR + kalibrasi threshold
- Protokol pengumpulan data

## Dokumen terkait (di main, milik bersama)

- [docs/DESAIN.md](../docs/DESAIN.md) — desain teknis sistem
- [docs/API.md](../docs/API.md) — kontrak API untuk mobile
- [docs/PENGUMPULAN_DATA.md](../docs/PENGUMPULAN_DATA.md) — protokol data & evaluasi

## Kontak

Amin (@drafi19) — bagian AI/ML.
