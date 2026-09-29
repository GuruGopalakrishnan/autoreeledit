# autoreel

AI-powered auto-editor for talking-head videos. Upload a video, pick a caption style (or let it auto-pick per moment), and get back a captioned, person-segmented edit — offline, no API calls except the one-time Whisper/MediaPipe model downloads.

Two parts:

- **`backend/`** — Python/FastAPI. Whisper transcription, MediaPipe person segmentation + face/pose detection, Pillow-rendered animated captions, OpenCV compositing, ffmpeg audio mux. See `backend/README.md`.
- **`frontend/`** — Next.js. Upload UI, job progress, result preview/download. Talks to the backend over HTTP.

## Quickstart

**Backend** (needs `ffmpeg` on `PATH`):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py          # http://localhost:8000
```

**Frontend** (separate terminal):

```bash
cd frontend
npm install
npm run dev             # http://localhost:3000
```

Open `http://localhost:3000`, upload a video, pick a style, and watch it process.

## Status

This is being built in phases:

- [x] **Phase 1** — Project Setup: upload, style pick, auto-prepare, result preview/download
- [ ] Style Gallery with live animated previews
- [ ] Full timeline editor (transcript/caption/keyword/animation tracks, Caption Inspector panel)
- [ ] Subject Mask & Track panel (hand tracking, "text behind subject" compositing)
- [ ] Title Moments gallery (starburst, cutout title, black pause, before/after)
