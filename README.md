# AI Shorts Factory

AI Shorts Factory is a production-oriented n8n + Python automation system for creating batches of 10 YouTube Shorts from trend research through scheduled upload.

## What one click does

The master n8n workflow runs the complete pipeline:

1. Researches trending topics from Google News/Trends-style RSS, Reddit technology, Hacker News, and RSS feeds.
2. Deduplicates and selects 10 topics.
3. Generates Shorts metadata and 40-second scripts.
4. Synthesizes cloned speech with F5-TTS and normalizes WAV audio.
5. Generates SRT/ASS captions with word-paced timing.
6. Downloads stock media or uses local fallback assets.
7. Renders 1080x1920 60fps videos with FFmpeg and burned captions.
8. Generates thumbnails.
9. Uploads/schedules videos with the YouTube Data API.
10. Writes JSONL event logs and used-topic state for resume and duplicate avoidance.

## Repository layout

- `workflows/08_Master_Workflow.json` is the only n8n workflow; it orchestrates the Python application with standard Execute Command nodes.
- `scripts/` Python automation modules and batch entry points.
- `config/` runtime settings and environment template.
- `prompts/` Gemini prompt templates.
- `assets/` local reference voice and fallback stock media.
- `audio/`, `videos/`, `captions/`, `thumbnails/`, `output/`, `temp/`, `logs/`, `state/`, `cache/` generated/runtime folders.
- `docs/` installation, setup, architecture, and troubleshooting documentation.

## Quick start on Windows 10

```powershell
cd "D:\EDITING & WEB DEVOLOPMENTS\N8N-YT-SHORTS"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy config\.env.example .env
notepad .env
n8n import:workflow --input workflows\08_Master_Workflow.json
n8n start
```

Open n8n, configure environment variables, then run **08 Master Workflow**. Do not import old 01-07 workflows; the system is Python-first now.

## Direct CLI run

```powershell
python scripts\research_engine.py --limit 10 --output output\topics.json
python scripts\script_generator.py --topics output\topics.json --output output\scripts.json
python scripts\scheduler.py --queue output\scripts.json --upload
```

See `docs/SETUP.md` before enabling uploads.
