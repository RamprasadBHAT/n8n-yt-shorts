# Troubleshooting

- **FFmpeg not found**: set `ffmpeg_path` and `ffprobe_path` in `config/settings.json` to absolute `.exe` paths.
- **F5-TTS fails**: verify the configured command works in the same terminal as n8n and that reference audio/text files exist.
- **No stock media**: set `PEXELS_API_KEY` or add `.mp4`, `.jpg`, or `.png` files to `assets/stock/`.
- **YouTube OAuth opens browser on server**: create `config/youtube_token.json` locally and copy it to the automation machine.
- **Duplicate topics skipped**: clear `state/used_topics.json` only if you intentionally want to allow repeats.
- **n8n Execute Command cannot find Python**: use an absolute Python executable path in workflow command nodes.
