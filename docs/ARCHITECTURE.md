# Architecture

```mermaid
flowchart TD
  A[08 Master Workflow in n8n] --> B[research_engine.py]
  B --> C[script_generator.py]
  C --> D[voice.py]
  D --> E[subtitles.py]
  E --> F[render_video.py]
  F --> G[generate_thumbnail.py]
  G --> H[youtube_upload.py]
  H --> I[logs + state]
```

The system is Python-first. n8n is intentionally small and reliable: it uses only standard trigger, set, execute-command, read-file, and code nodes to run complete Python programs in sequence. All API integrations, retries, duplicate detection, rendering, caption generation, thumbnail creation, scheduling, and uploads live in Python.
