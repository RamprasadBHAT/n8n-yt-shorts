# Architecture

```mermaid
flowchart TD
  A[08 Master Workflow] --> B[01 Research Engine]
  B --> C[02 Script Generator]
  C --> D[03 F5-TTS Voice]
  D --> E[04 Subtitles]
  E --> F[05 Video Generator]
  F --> G[06 Thumbnail Generator]
  G --> H[07 YouTube Uploader]
  H --> I[Logs + State]
```

The n8n layer orchestrates idempotent Python scripts. Python owns API calls, media processing, retry behavior, filesystem state, and upload logic. Generated artifacts are stored in deterministic folders by job id, allowing failed runs to be resumed or repeated safely.
