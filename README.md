# ClipForge AI

A self-hostable, mobile-friendly gaming clip web app.

## What works
- YouTube URL input via `yt-dlp` and local video upload.
- Five candidate highlights selected with an audio-energy heuristic.
- Vertical 1080x1920 H.264/AAC MP4 output.
- Optional speech transcription using local `faster-whisper` (first run downloads the selected model).
- Preview and download generated clips.

## Important limitations
- Highlight selection is an audio-loudness heuristic, not a trained semantic AI model. It can miss visual-only moments and may choose loud music or explosions.
- Caption editing in this starter changes the SRT subtitle file. It does **not** automatically re-render the MP4; re-render support should be added before treating edited captions as burned-in exports.
- If Whisper is not installed or cannot run, clips are generated without speech captions.
- YouTube downloading is not guaranteed: availability, age/login restrictions, regional blocks, rate limits, and YouTube changes can prevent it. Use only content you own or have permission to process and comply with platform terms and applicable law.
- This is a starter application, not a hosted public website. Deploy it to a server with FFmpeg, disk space, CPU/RAM, HTTPS, and background-job handling for real use. Do not expose an unauthenticated public instance to the internet.

## Run locally
Requires Python 3.11+ and FFmpeg/ffprobe installed.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000` on the computer. For phone testing on the same Wi-Fi, open `http://COMPUTER-LAN-IP:5000`.

## Docker
```bash
docker build -t clipforge-ai .
docker run --rm -p 5000:5000 -v "$PWD/uploads:/app/uploads" -v "$PWD/outputs:/app/outputs" clipforge-ai
```

## Production checklist
- Add authentication, rate limits, CSRF protection, per-user quotas, cleanup jobs, and private job storage.
- Run video work in a background queue (Celery/RQ) with progress updates.
- Add a proper subtitle editor and re-render endpoint for burned-in caption changes.
- Set upload size, duration, and disk quotas.
- Use a persistent volume; ephemeral free hosting may delete uploaded/generated files.
- Review hosting provider terms and free-tier limits. Video processing may exceed free-tier CPU, memory, storage, or time limits.
