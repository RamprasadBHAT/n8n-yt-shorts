# Setup Guide

1. Add your F5-TTS voice reference WAV at `assets/voice/reference.wav` and matching transcript at `assets/voice/reference.txt`.
2. Set `GEMINI_API_KEY` for AI ranking and generation extensions.
3. Set `PEXELS_API_KEY` or place fallback vertical clips/images in `assets/stock/`.
4. Create a YouTube OAuth desktop credential, save it as `config/youtube_client_secret.json`, and run the uploader once interactively to create `config/youtube_token.json`.
5. Review `config/settings.json` for paths, render dimensions, schedule spacing, retry attempts, and privacy status.
6. Run the master workflow in n8n.

The default YouTube privacy is `private` for safe production validation before public publishing.
