from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config import ConfigError, Settings, load_settings

try:
    from logging import get_logger, write_event
except ImportError:  # pytest may import stdlib logging before scripts/logging.py
    import importlib.util

    _logging_path = Path(__file__).resolve().with_name("logging.py")
    _spec = importlib.util.spec_from_file_location("factory_logging", _logging_path)
    _factory_logging = importlib.util.module_from_spec(_spec)
    assert _spec and _spec.loader
    _spec.loader.exec_module(_factory_logging)
    get_logger = _factory_logging.get_logger
    write_event = _factory_logging.write_event


@dataclass(frozen=True)
class SubtitleConfig:
    scripts_file: Path
    audio_dir: Path
    captions_dir: Path
    ffprobe_path: str
    default_duration_seconds: float
    max_items: int
    words_per_caption: int
    max_caption_seconds: float
    ass_style: str


@dataclass(frozen=True)
class WordTiming:
    word: str
    start: float
    end: float


@dataclass(frozen=True)
class CaptionSegment:
    index: int
    start: float
    end: float
    text: str


def load_subtitle_config(settings: Settings, input_override: str | None = None, audio_dir_override: str | None = None, output_dir_override: str | None = None) -> SubtitleConfig:
    cfg = settings.get("subtitles", {}) or {}
    return SubtitleConfig(
        scripts_file=settings.resolve_path(input_override or cfg.get("scripts_file", "output/scripts.json")),
        audio_dir=settings.resolve_path(audio_dir_override or cfg.get("audio_dir", settings.get("folders.audio", "audio"))),
        captions_dir=settings.resolve_path(output_dir_override or cfg.get("output_dir", settings.get("folders.captions", "captions"))),
        ffprobe_path=str(settings.get("ffprobe_path", "ffprobe")),
        default_duration_seconds=float(cfg.get("default_duration_seconds", settings.get("rendering.duration_seconds", 40))),
        max_items=int(cfg.get("max_items", settings.get("videos_per_batch", 10))),
        words_per_caption=int(cfg.get("words_per_caption", 6)),
        max_caption_seconds=float(cfg.get("max_caption_seconds", 3.2)),
        ass_style=str(cfg.get("ass_style", settings.get("rendering.subtitle_style", "Fontname=Arial,Fontsize=74,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=5,Shadow=0,Alignment=2,MarginV=210"))),
    )


def validate_config(config: SubtitleConfig) -> None:
    if not config.scripts_file.exists():
        raise FileNotFoundError(f"Scripts file not found: {config.scripts_file}")
    if not config.audio_dir.exists():
        raise FileNotFoundError(f"Audio directory not found: {config.audio_dir}")
    if config.default_duration_seconds <= 0:
        raise ConfigError("subtitles.default_duration_seconds must be greater than zero")
    if config.max_items < 1:
        raise ConfigError("subtitles.max_items must be greater than zero")
    if config.words_per_caption < 1:
        raise ConfigError("subtitles.words_per_caption must be greater than zero")
    if config.max_caption_seconds <= 0:
        raise ConfigError("subtitles.max_caption_seconds must be greater than zero")


def load_scripts(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Scripts input must be a JSON array")
    if not data:
        raise ValueError("Scripts input is empty")
    for index, record in enumerate(data, 1):
        if not isinstance(record, dict):
            raise ValueError(f"Script #{index} must be a JSON object")
        if not str(record.get("id", "")).strip():
            raise ValueError(f"Script #{index} is missing a non-empty id")
        if not str(record.get("script", "")).strip():
            raise ValueError(f"Script #{index} is missing non-empty script text")
    return data


def safe_job_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip())
    return cleaned.strip("-")[:80] or "caption-job"


def audio_path_for(record: dict[str, Any], audio_dir: Path) -> Path:
    explicit = record.get("audio_path") or record.get("voice_path")
    if explicit:
        path = Path(str(explicit))
        return path if path.is_absolute() else audio_dir.parent / path
    return audio_dir / f"{safe_job_id(str(record['id']))}.wav"


def probe_duration(audio_path: Path, config: SubtitleConfig, logger: Any) -> float:
    command = [config.ffprobe_path, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        duration = float(completed.stdout.strip())
        if duration > 0:
            return duration
    except (FileNotFoundError, subprocess.CalledProcessError, ValueError) as exc:
        logger.warning("ffprobe_duration_failed audio=%s error=%s", audio_path, exc)
    try:
        with wave.open(str(audio_path), "rb") as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            if frames > 0 and rate > 0:
                return frames / float(rate)
    except (wave.Error, EOFError, OSError) as exc:
        logger.warning("wave_duration_failed audio=%s error=%s using_default=%s", audio_path, exc, config.default_duration_seconds)
    return config.default_duration_seconds


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)?|[&%$#@]+|[^\s]", text)


def generate_word_timings(text: str, duration: float) -> list[WordTiming]:
    words = [token for token in tokenize(text) if re.search(r"[A-Za-z0-9]", token)]
    if not words:
        return []
    gap = 0.035
    usable = max(duration - gap * max(len(words) - 1, 0), duration * 0.82)
    total_weight = sum(max(len(word), 3) for word in words)
    cursor = 0.0
    timings: list[WordTiming] = []
    for word in words:
        word_duration = max(0.12, usable * max(len(word), 3) / total_weight)
        start = min(cursor, duration)
        end = min(start + word_duration, duration)
        timings.append(WordTiming(word=word, start=round(start, 3), end=round(max(end, start + 0.08), 3)))
        cursor = end + gap
    if timings:
        last = timings[-1]
        timings[-1] = WordTiming(last.word, last.start, round(duration, 3))
    return timings


def build_segments(words: list[WordTiming], words_per_caption: int, max_caption_seconds: float) -> list[CaptionSegment]:
    segments: list[CaptionSegment] = []
    current: list[WordTiming] = []
    for word in words:
        current.append(word)
        elapsed = current[-1].end - current[0].start
        boundary = len(current) >= words_per_caption or elapsed >= max_caption_seconds or re.search(r"[.!?]$", word.word)
        if boundary:
            segments.append(segment_from_words(len(segments) + 1, current))
            current = []
    if current:
        segments.append(segment_from_words(len(segments) + 1, current))
    return segments


def segment_from_words(index: int, words: list[WordTiming]) -> CaptionSegment:
    return CaptionSegment(index=index, start=words[0].start, end=words[-1].end, text=" ".join(word.word for word in words))


def format_srt_time(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def format_ass_time(seconds: float) -> str:
    total_cs = max(0, round(seconds * 100))
    hours, remainder = divmod(total_cs, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    secs, centis = divmod(remainder, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{centis:02}"


def write_srt(segments: list[CaptionSegment], path: Path) -> None:
    blocks = [f"{segment.index}\n{format_srt_time(segment.start)} --> {format_srt_time(segment.end)}\n{segment.text}" for segment in segments]
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def parse_ass_style(style: str) -> dict[str, str]:
    defaults = {
        "Fontname": "Arial",
        "Fontsize": "74",
        "PrimaryColour": "&H00FFFFFF",
        "SecondaryColour": "&H0000FFFF",
        "OutlineColour": "&H00000000",
        "BackColour": "&H80000000",
        "Bold": "1",
        "Italic": "0",
        "Underline": "0",
        "StrikeOut": "0",
        "ScaleX": "100",
        "ScaleY": "100",
        "Spacing": "0",
        "Angle": "0",
        "BorderStyle": "1",
        "Outline": "5",
        "Shadow": "0",
        "Alignment": "2",
        "MarginL": "80",
        "MarginR": "80",
        "MarginV": "210",
        "Encoding": "1",
    }
    for item in style.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            key = key.strip()
            if key in defaults and value.strip():
                defaults[key] = value.strip()
    return defaults


def ass_header(style: str) -> str:
    fields = [
        "Fontname",
        "Fontsize",
        "PrimaryColour",
        "SecondaryColour",
        "OutlineColour",
        "BackColour",
        "Bold",
        "Italic",
        "Underline",
        "StrikeOut",
        "ScaleX",
        "ScaleY",
        "Spacing",
        "Angle",
        "BorderStyle",
        "Outline",
        "Shadow",
        "Alignment",
        "MarginL",
        "MarginR",
        "MarginV",
        "Encoding",
    ]
    parsed = parse_ass_style(style)
    values = ", ".join(parsed[field] for field in fields)
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        f"Format: Name, {', '.join(fields)}\n"
        f"Style: Default, {values}\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def escape_ass(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def write_ass(segments: list[CaptionSegment], path: Path, style: str) -> None:
    lines = [ass_header(style)]
    for segment in segments:
        lines.append(f"Dialogue: 0,{format_ass_time(segment.start)},{format_ass_time(segment.end)},Default,,0,0,0,,{escape_ass(segment.text)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_words_json(words: list[WordTiming], path: Path) -> None:
    path.write_text(json.dumps([word.__dict__ for word in words], indent=2, ensure_ascii=False), encoding="utf-8")


def generate_for_script(record: dict[str, Any], config: SubtitleConfig, logger: Any) -> dict[str, Any]:
    job_id = safe_job_id(str(record["id"]))
    audio_path = audio_path_for(record, config.audio_dir)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file for script {record['id']} not found: {audio_path}")
    duration = probe_duration(audio_path, config, logger)
    words = generate_word_timings(str(record["script"]), duration)
    if not words:
        raise ValueError(f"Script {record['id']} produced no subtitle words")
    segments = build_segments(words, config.words_per_caption, config.max_caption_seconds)
    config.captions_dir.mkdir(parents=True, exist_ok=True)
    srt_path = config.captions_dir / f"{job_id}.srt"
    ass_path = config.captions_dir / f"{job_id}.ass"
    words_path = config.captions_dir / f"{job_id}.words.json"
    write_srt(segments, srt_path)
    write_ass(segments, ass_path, config.ass_style)
    write_words_json(words, words_path)
    result = {"id": record["id"], "audio": str(audio_path), "srt": str(srt_path), "ass": str(ass_path), "words": str(words_path), "duration_seconds": duration, "segments": len(segments), "word_count": len(words)}
    write_event("subtitles_generated", result)
    logger.info("subtitles_generated id=%s srt=%s ass=%s words=%s", record["id"], srt_path, ass_path, words_path)
    return result


def generate_batch(config: SubtitleConfig, logger: Any, limit: int | None = None) -> list[dict[str, Any]]:
    validate_config(config)
    scripts = load_scripts(config.scripts_file)
    batch_limit = limit if limit is not None else config.max_items
    if batch_limit < 1:
        raise ValueError("--limit must be greater than zero")
    return [generate_for_script(record, config, logger) for record in scripts[:batch_limit]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate SRT, ASS, and word-timestamp subtitle files for Shorts audio.")
    parser.add_argument("--config", default="config/settings.json", help="Path to settings.json")
    parser.add_argument("--input", default=None, help="Input scripts JSON file, defaults to subtitles.scripts_file or output/scripts.json")
    parser.add_argument("--audio-dir", default=None, help="Directory containing generated WAV files, defaults to audio/")
    parser.add_argument("--output-dir", default=None, help="Directory for caption outputs, defaults to captions/")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of Shorts to process")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
        logger = get_logger("subtitles")
        config = load_subtitle_config(settings, args.input, args.audio_dir, args.output_dir)
        results = generate_batch(config, logger, args.limit)
        manifest = config.captions_dir / "manifest.json"
        manifest.write_text(json.dumps({"count": len(results), "items": results}, indent=2), encoding="utf-8")
        write_event("subtitles_batch_generated", {"count": len(results), "manifest": str(manifest)})
        print(json.dumps({"count": len(results), "items": results, "manifest": str(manifest)}, indent=2))
        return 0
    except (ConfigError, FileNotFoundError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"subtitles failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
