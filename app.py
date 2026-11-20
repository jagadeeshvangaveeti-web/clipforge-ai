import os, uuid, json, re, subprocess, shutil
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename

BASE = Path(__file__).resolve().parent
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
for p in (UPLOADS, OUTPUTS): p.mkdir(exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024
JOBS = {}

def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, check=True)

def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(path)]).stdout.strip()
    return float(out)

def download_youtube(url, dest):
    # yt-dlp respects YouTube's access controls; use only videos you own or have permission to use.
    run(["yt-dlp", "--no-playlist", "-f", "bv*[height<=1080]+ba/b[height<=1080]",
         "--merge-output-format", "mp4", "-o", str(dest), url])
    if not dest.exists():
        candidates = list(dest.parent.glob(dest.stem + ".*"))
        if candidates:
            candidates[0].rename(dest)
    if not dest.exists(): raise RuntimeError("Download did not produce an MP4 file.")

def detect_highlights(video, count=5):
    """
    Lightweight local highlight picker: samples audio loudness in short windows,
    then selects high-energy moments with spacing. This is an automatic heuristic,
    not a semantic understanding of game events.
    """
    dur = duration(video)
    if dur < 8: return [(0, max(1, dur))]
    step = 2.0
    scores = []
    t = 0.0
    while t < dur:
        length = min(step, dur - t)
        try:
            s = run(["ffmpeg", "-ss", str(t), "-t", str(length), "-i", str(video),
                     "-vn", "-af", "volumedetect", "-f", "null", "-"])
            txt = s.stderr
            m = re.search(r"mean_volume:\s*(-?[\d.]+)\s*dB", txt)
            peak = re.search(r"max_volume:\s*(-?[\d.]+)\s*dB", txt)
            mean = float(m.group(1)) if m else -60
            pk = float(peak.group(1)) if peak else -60
            scores.append((t, (mean + 60) * .6 + (pk + 60) * .4))
        except Exception:
            scores.append((t, 0))
        t += step
    clip_len = min(35.0, max(12.0, dur / max(count, 1)))
    candidates = sorted(scores, key=lambda x: x[1], reverse=True)
    chosen = []
    for start, score in candidates:
        center = start + step / 2
        a = max(0, min(dur - clip_len, center - clip_len / 2))
        if all(abs(a - old) > clip_len * .75 for old in chosen):
            chosen.append(a)
        if len(chosen) == count: break
    while len(chosen) < count:
        a = max(0, (dur - clip_len) * len(chosen) / max(1, count - 1))
        if all(abs(a - old) > 1 for old in chosen): chosen.append(a)
        else: break
    return [(a, min(clip_len, dur-a)) for a in sorted(chosen)]

def make_srt(video, start, length, srt_path):
    # Optional Whisper transcription; if unavailable, create a blank subtitle file.
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(os.getenv("WHISPER_MODEL", "tiny"), device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(video), language=None, vad_filter=True)
        rows, idx = [], 1
        for seg in segments:
            a, b = max(seg.start, start), min(seg.end, start + length)
            if b <= a: continue
            txt = seg.text.strip().replace("-->", "→")
            def ts(x):
                ms = int(round(x * 1000))
                h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
                return f"{h:02}:{m:02}:{s:02},{ms:03}"
            rows.append(f"{idx}\n{ts(a-start)} --> {ts(b-start)}\n{txt}\n")
            idx += 1
        srt_path.write_text("\n".join(rows), encoding="utf-8")
        return bool(rows)
    except Exception:
        srt_path.write_text("", encoding="utf-8")
        return False

@app.get("/")
def home():
    return render_template("index.html")

@app.post("/api/create")
def create():
    source = request.form.get("source", "").strip()
    url = request.form.get("url", "").strip()
    f = request.files.get("video")
    if not source and not (f and f.filename):
        return jsonify(error="Paste a YouTube URL or choose an MP4 video."), 400
    job = uuid.uuid4().hex[:10]
    jobdir = OUTPUTS / job
    jobdir.mkdir(parents=True)
    input_path = UPLOADS / f"{job}.mp4"
    try:
        if f and f.filename:
            if not f.filename.lower().endswith((".mp4", ".mov", ".mkv", ".webm")):
                raise ValueError("Please upload an MP4, MOV, MKV or WebM video.")
            f.save(input_path)
        elif source:
            if not re.match(r"^https?://", source):
                raise ValueError("Please enter a valid http(s) video URL.")
            download_youtube(source, input_path)
        total = duration(input_path)
        if total <= 0: raise ValueError("Could not read video duration.")
        clips, items = detect_highlights(input_path, 5), []
        for i, (start, length) in enumerate(clips, 1):
            name = f"clip_{i}.mp4"
            srt = jobdir / f"clip_{i}.srt"
            has_caps = make_srt(input_path, start, length, srt)
            out = jobdir / name
            # Burn captions when Whisper is installed and returned text.
            vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
            if has_caps:
                escaped_srt = str(srt).replace("\\\\", "/").replace(":", "\\\\:")
                vf += f",subtitles='{escaped_srt}':force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2,MarginV=150'"
            run(["ffmpeg", "-y", "-ss", str(start), "-i", str(input_path), "-t", str(length),
                 "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                 "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)])
            items.append({"id": i, "file": f"/media/{job}/{name}", "start": round(start,1),
                          "duration": round(length,1), "captions": has_caps,
                          "srt": f"/captions/{job}/clip_{i}.srt"})
        JOBS[job] = {"items": items, "input": str(input_path), "dir": str(jobdir)}
        return jsonify(job=job, clips=items,
                       note="Highlights are selected using audio-energy peaks. Install the optional Whisper model for automatic speech captions.")
    except Exception as e:
        shutil.rmtree(jobdir, ignore_errors=True)
        input_path.unlink(missing_ok=True)
        return jsonify(error=str(e)), 500

@app.get("/media/<job>/<filename>")
def media(job, filename):
    if job not in JOBS: abort(404)
    return send_from_directory(OUTPUTS / job, filename, as_attachment=False)

@app.get("/captions/<job>/<filename>")
def get_caption(job, filename):
    if job not in JOBS: abort(404)
    return send_from_directory(OUTPUTS / job, filename, mimetype="text/plain")

@app.post("/api/caption")
def edit_caption():
    data = request.get_json(force=True)
    job, clip = data.get("job"), int(data.get("clip", 0))
    text = data.get("text", "")
    if job not in JOBS or not 1 <= clip <= 5: return jsonify(error="Unknown clip"), 404
    srt = OUTPUTS / job / f"clip_{clip}.srt"
    # Simple editor: replace subtitle text while retaining timing; safe SRT text only.
    content = srt.read_text(encoding="utf-8") if srt.exists() else ""
    lines = content.splitlines()
    blocks, current = [], []
    for line in lines + [""]:
        if line.strip() == "":
            if current: blocks.append(current); current=[]
        else: current.append(line)
    if not blocks:
        return jsonify(error="No speech captions found. Install Whisper and regenerate to create editable timed captions."), 400
    for b in blocks: b[2:] = [text]
    srt.write_text("\n\n".join("\n".join(b) for b in blocks) + "\n", encoding="utf-8")
    return jsonify(ok=True, message="Caption text updated in the subtitle file. Re-rendering is required to burn edits into the MP4.")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
