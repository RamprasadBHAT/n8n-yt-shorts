# Phase 2: Script Generator

Phase 2 converts `output/topics.json` into complete YouTube Shorts packages in `output/scripts.json`.

The generator is Python-first and can be run directly or by the n8n master workflow:

```bash
python scripts/script_generator.py --topics output/topics.json --output output/scripts.json
```

## Behavior

For every researched topic, the generator produces:

- title
- hook
- 40-second voiceover script
- description
- CTA
- hashtags
- timed visual beats for downstream video rendering

When the configured Gemini API key exists, the generator asks Gemini for strict JSON using `prompts/script_prompt.txt`. If Gemini is unavailable or returns invalid content, the generator logs the issue and uses a deterministic local script builder so the batch remains runnable.

## Configuration

All behavior is controlled by the `script_generation` section in `config/settings.json`, including input/output paths, prompt path, duration, speech rate, title length, tone, CTA, hashtags, and Gemini temperature.
