# Phase 3: Voice Generation

Phase 3 converts `output/scripts.json` into one normalized WAV voiceover per script in `audio/`.

```bash
python scripts/voice.py --input output/scripts.json --output-dir audio --overwrite
```

## Behavior

- Reads the full script batch from `output/scripts.json`.
- Uses F5-TTS with the cloned voice reference configured in `config/settings.json`.
- Generates a raw temporary WAV in `temp/` for each script.
- Normalizes loudness with FFmpeg `loudnorm` and writes final WAV files to `audio/`.
- Skips existing WAV files unless `--overwrite` is provided.
- Writes `audio/manifest.json` and JSONL events for generated files and completed batches.

## Configuration

The `voice` section controls the cloned voice and output format:

- `reference_audio`: cloned voice reference WAV.
- `reference_text`: transcript of the reference audio.
- `speaker`: F5-TTS speaker name.
- `speed`: synthesis speed multiplier.
- `normalize_lufs`: integrated loudness target.
- `sample_rate`: final WAV sample rate.
- `channels`: final channel count.
- `input_file`: default scripts input.
- `output_dir`: default WAV output directory.

The `f5_tts.command` setting selects the F5-TTS executable. `f5_tts.extra_args` can pass additional production F5-TTS flags without code changes.
