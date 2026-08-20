# Phase 4: Subtitles

Phase 4 converts the script packages in `output/scripts.json` and the generated WAV files in `audio/` into caption assets in `captions/`.

```bash
python scripts/subtitles.py --input output/scripts.json --audio-dir audio --output-dir captions
```

## Outputs

For each Short, the module writes:

- `<id>.srt`: standard subtitle file for upload and review.
- `<id>.ass`: styled subtitle file for FFmpeg burn-in.
- `<id>.words.json`: word-level timestamp data for animated captions.
- `manifest.json`: batch summary of generated caption files.

## Timing strategy

The module probes each WAV duration with `ffprobe` and aligns the script text across the actual audio duration. This produces deterministic word-level timestamps without adding non-standard dependencies. If `ffprobe` is unavailable in a test or restricted environment, the configured default duration is used and a warning is logged.

## Configuration

The `subtitles` section in `config/settings.json` controls input/output paths, max batch size, caption chunking, fallback duration, and ASS styling. FFprobe is configured globally through `ffprobe_path`.
