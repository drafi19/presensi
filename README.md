# Presensi — Face Recognition Attendance System

A clock-in/clock-out attendance system that verifies users by face.
Users record a short video on their phone; a Python server runs
detection → anti-spoofing → face embedding → matching, and records the
result in a server-side audit log.

> Status: v1 design finalized — implementation starting.
> Full technical design: [docs/DESAIN.md](docs/DESAIN.md)

## How it works

1. User logs in on the mobile app (the account binds the device to a `user_id`).
2. The app verifies the user is inside the work area (GPS/geofence — app side).
3. The app records ~2 seconds of video and sends sampled JPEG frames + `user_id` to the API.
4. The server pipeline, per frame:
   - face detection (SCRFD)
   - anti-spoofing (MiniFASNet — rejects photo/replay attacks)
   - face embedding (ArcFace, 512-d)
   - cosine-similarity matching against the enrolled gallery (1:1 verification)
   - per-frame voting (median similarity + ≥70% consensus)
5. Server returns `match | no_match | spoof | no_face | low_quality` and
   writes an audit-log entry. Attendance records are derived from server
   logs, not app claims.

## Tech stack

- Python · FastAPI · onnxruntime (CPU)
- InsightFace `buffalo_l` (SCRFD detection + ArcFace embedding)
- MiniFASNet (Silent-Face-Anti-Spoofing)
- SQLite + NumPy embedding gallery

## Repository layout

```
docs/          technical design documents
src/presensi/  API, pipeline, storage, quality gates   (WIP)
scripts/       enrollment / evaluation / tuning CLIs   (WIP)
tests/         unit & integration tests                (WIP)
```

## Team

- [@drafi19](https://github.com/drafi19) — AI/ML: detection, anti-spoofing,
  embedding, matching, evaluation
- Raihan — Mobile development: app, auth, GPS/geofence

## Roadmap

M1 environment + models running → M2 pipeline + gallery → M3 API + audit log →
M4 data collection + FAR/FRR evaluation + threshold tuning → M5 (optional)
live WebSocket, anti-spoof fine-tuning
