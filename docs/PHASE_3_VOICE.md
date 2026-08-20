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
- `speaker`: retained as channel metadata, but not passed to `f5-tts_infer-cli` because F5-TTS 1.1.22 does not support `--speaker`.
- `speed`: retained as channel metadata, but not passed to `f5-tts_infer-cli` because F5-TTS 1.1.22 does not support `--speed`.
- `normalize_lufs`: integrated loudness target.
- `sample_rate`: final WAV sample rate.
- `channels`: final channel count.
- `input_file`: default scripts input.
- `output_dir`: default WAV output directory.

The `f5_tts.command` setting selects the F5-TTS executable.

## F5-TTS CLI compatibility

The F5-TTS invocation intentionally uses only the installed 1.1.22-compatible synthesis flags: `--ref_audio`, `--ref_text`, `--gen_text`, and `--output_file`. The module does not pass `--speaker` because the installed CLI rejects it.
