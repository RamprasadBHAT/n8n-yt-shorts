# Installation Guide

## Prerequisites

- Windows 10 with PowerShell.
- Python 3.11+.
- n8n installed globally or via Docker Desktop.
- FFmpeg and FFprobe on `PATH` or configured in `config/settings.json`.
- F5-TTS installed and callable from the configured command.
- Whisper CLI if you replace the built-in timed caption generator with transcription.

## Python setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## Environment setup

Copy `config/.env.example` to `.env` and fill in API keys. Keep `.env` out of Git.

## n8n import

Import all workflow JSON files from `workflows/`, or import `08_Master_Workflow.json` for the one-click pipeline.
