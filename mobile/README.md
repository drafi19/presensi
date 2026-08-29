# `mobile/` — Aplikasi Mobile (bagian Raihan)

> Folder ini untuk aplikasi mobile (Flutter/React Native — menyesuaikan
> pilihan Raihan). Belum ada kode; struktur `lib/` dan `assets/` disiapkan.

## Tugas mobile (dari desain bersama — docs/DESAIN.md §1)

1. Login/akun — mengikat HP ke `user_id`
2. Validasi GPS/geofence "user ada di area kerja"
3. Rekam ±2 detik → kirim batch frame JPEG + `user_id` ke API
4. Tampilkan verdict: `match / no_match / spoof / no_face / low_quality`
   (panduan UI per status ada di [docs/API.md](../docs/API.md))

## Integrasi API

Kontrak lengkap: **[docs/API.md](../docs/API.md)** (endpoint, format,
error code, contoh curl). Server dev bisa dinyalakan oleh tim AI kapan saja
untuk testing — koordinasi via chat.

Catatan penting (dari kontrak): app **tidak** melakukan matching lokal —
semua keputusan dari server; record presensi resmi diturunkan dari log server.
