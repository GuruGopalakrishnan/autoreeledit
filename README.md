# autoreel

AI-powered auto-editor for talking-head videos. Upload a video, pick a caption style (or let it auto-pick per moment), and get back a captioned, person-segmented edit — offline, no API calls except the one-time Whisper/MediaPipe model downloads.

Two parts:

- **`backend/`** — Python/FastAPI. Whisper transcription, MediaPipe person segmentation + face/pose/hand detection, Pillow-rendered animated captions, OpenCV compositing, ffmpeg audio mux.
- **`frontend/`** — Next.js. Upload UI, timeline editor, job progress, result preview/download. Talks to the backend over HTTP.

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

Open `http://localhost:3000`, upload a video and (optionally) a transcript, then **Open Editor** — it transcribes/parses, then drops you into the timeline editor to review captions, pick a style, and export.

## Status

This is being built in phases:

- [x] **Phase 1** — Project Setup: upload, transcript upload/paste
- [x] **Phase 2** — Style Gallery: 10 selectable presets with live animated preview cards, Auto-switch toggle
- [x] **Phase 3** — Timeline editor: caption timeline (click to seek/select), Caption Inspector (edit text, force/clear Dramatic), export
- [x] **Phase 4** — Subject Mask & Track: hand tracking (avoids captions overlapping hands), mask edge outline, text-behind-subject compositing
- [x] **Phase 5** — Title Moments: apply Starburst / Cutout Title / Black Pause to one specific caption from the Caption Inspector, overriding the auto-triggers for just that moment

All five roadmap phases are done. Ideas for what's next: a real "before/after" comparison view in the editor, more Title Moment presets, batch-applying a moment to multiple captions at once.
