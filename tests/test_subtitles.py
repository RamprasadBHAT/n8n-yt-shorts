from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from config import load_settings
from subtitles import build_segments, format_ass_time, format_srt_time, generate_batch, generate_word_timings, load_subtitle_config, main


def write_settings(tmp_path: Path) -> Path:
    settings = {
        "videos_per_batch": 10,
        "folders": {"output": "output", "audio": "audio", "captions": "captions", "logs": "logs", "temp": "temp"},
        "logging": {"file": "logs/factory.log", "level": "INFO"},
        "ffprobe_path": "ffprobe-test",
        "rendering": {"duration_seconds": 40, "subtitle_style": "Fontname=Arial,Fontsize=74,MarginV=210"},
        "subtitles": {
            "scripts_file": "output/scripts.json",
            "audio_dir": "audio",
            "output_dir": "captions",
            "default_duration_seconds": 12,
            "max_items": 10,
            "words_per_caption": 4,
            "max_caption_seconds": 2.5,
        },
    }
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(settings), encoding="utf-8")
    return path


def sample_scripts() -> list[dict[str, str]]:
    return [
        {"id": "alpha", "script": "AI tools are changing creator workflows faster than expected today."},
        {"id": "beta/item", "script": "Automation helps teams test ideas, verify facts, and publish consistently."},
    ]


def test_time_formatters() -> None:
    assert format_srt_time(65.432) == "00:01:05,432"
    assert format_ass_time(65.43) == "0:01:05.43"


def test_word_timings_and_segments_are_monotonic() -> None:
    words = generate_word_timings("One two three four five six seven eight.", 8.0)
    assert words[0].start == 0
    assert words[-1].end == 8.0
    assert all(current.end <= nxt.start for current, nxt in zip(words, words[1:]))
    segments = build_segments(words, words_per_caption=3, max_caption_seconds=3)
    assert len(segments) == 3
    assert segments[0].text == "One two three"


def test_generate_batch_writes_srt_ass_and_word_json(tmp_path: Path, monkeypatch) -> None:
    settings_path = write_settings(tmp_path)
    scripts_path = tmp_path / "output" / "scripts.json"
    audio_dir = tmp_path / "audio"
    scripts_path.parent.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    scripts_path.write_text(json.dumps(sample_scripts()), encoding="utf-8")
    (audio_dir / "alpha.wav").write_bytes(b"RIFF")
    (audio_dir / "beta-item.wav").write_bytes(b"RIFF")

    monkeypatch.setattr("subtitles.probe_duration", lambda audio_path, config, logger: 10.0)
    settings = load_settings(settings_path)
    results = generate_batch(load_subtitle_config(settings), logger=type("Log", (), {"info": lambda *a, **k: None})())
    assert len(results) == 2
    assert (tmp_path / "captions" / "alpha.srt").read_text(encoding="utf-8").startswith("1\n00:00:00,000 -->")
    assert "[V4+ Styles]" in (tmp_path / "captions" / "alpha.ass").read_text(encoding="utf-8")
    words = json.loads((tmp_path / "captions" / "alpha.words.json").read_text(encoding="utf-8"))
    assert words[0]["word"] == "AI"


def test_main_processes_limit_and_manifest(tmp_path: Path, monkeypatch) -> None:
    settings_path = write_settings(tmp_path)
    scripts_path = tmp_path / "output" / "scripts.json"
    audio_dir = tmp_path / "audio"
    scripts_path.parent.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)
    scripts_path.write_text(json.dumps(sample_scripts()), encoding="utf-8")
    (audio_dir / "alpha.wav").write_bytes(b"RIFF")
    (audio_dir / "beta-item.wav").write_bytes(b"RIFF")
    monkeypatch.setattr("subtitles.probe_duration", lambda audio_path, config, logger: 9.5)

    assert main(["--config", str(settings_path), "--limit", "1"]) == 0
    manifest = json.loads((tmp_path / "captions" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["count"] == 1
    assert Path(manifest["items"][0]["srt"]).name == "alpha.srt"
