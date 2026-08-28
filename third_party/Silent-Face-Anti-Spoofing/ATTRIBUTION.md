# Attribution — Silent-Face-Anti-Spoofing

Folder ini berisi ekstraksi parsial dari repo:

- **Source**: https://github.com/minivision-ai/Silent-Face-Anti-Spoofing
- **License**: Apache License 2.0 (lihat `LICENSE` di folder ini)
- **Yang diambil**:
  - `src/model_lib/MiniFASNet.py` — definisi arsitektur MiniFASNet (dipakai
    oleh wrapper kita via `sys.path`)
  - `resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth` + `4_0_0_80x80_MiniFASNetV1SE.pth`
    — bobot pretrained resmi (ensemble yang sama dengan `test.py` upstream)
  - file `src/` lain yang ikut terekstrak (data_io, dst.) — referensi
- **Yang TIDAK diambil**: folder `saved_logs/` (berisi file yang namanya
  tidak valid di Windows) dan detector Caffe (`resources/detection_model/`,
  tidak dipakai — kita pakai SCRFD via insightface).

Wrapper inferensi kita: `src/presensi/pipeline/antispoof.py`
(mengikuti protokol inferensi upstream: transform ToTensor tanpa normalisasi,
crop 2.7x + full-frame, label 1 = real, ensemble jumlah softmax).

Catatan reproduksi: file `.pth` tidak ikut commit (lihat .gitignore) —
unduh ulang dari repo upstream bila folder `resources/anti_spoof_models/` kosong.

> Catatan license kejujuran: kami awalnya menyebut "MIT license" di dokumen
> desain; license resmi repo ini adalah Apache 2.0. Koreksi tercatat di sini.
