from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
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
class VoiceConfig:
    engine: str
    reference_audio: Path
    reference_text: Path
    normalize_lufs: float
    sample_rate: int
    channels: int
    input_file: Path
    output_dir: Path
    temp_dir: Path
    f5_command: str
    ffmpeg_path: str


def load_voice_config(settings: Settings, input_override: str | None = None, output_dir_override: str | None = None) -> VoiceConfig:
    voice = settings.get("voice", {}) or {}
    f5 = settings.get("f5_tts", {}) or {}
    return VoiceConfig(
        engine=str(voice.get("engine", "f5-tts")),
        reference_audio=settings.resolve_path(voice.get("reference_audio", "assets/voice/reference.wav")),
        reference_text=settings.resolve_path(voice.get("reference_text", "assets/voice/reference.txt")),
        normalize_lufs=float(voice.get("normalize_lufs", -16)),
        sample_rate=int(voice.get("sample_rate", 48000)),
        channels=int(voice.get("channels", 2)),
        input_file=settings.resolve_path(input_override or voice.get("input_file", "output/scripts.json")),
        output_dir=settings.resolve_path(output_dir_override or voice.get("output_dir", settings.get("folders.audio", "audio"))),
        temp_dir=settings.path("temp"),
        f5_command=str(f5.get("command", "f5-tts_infer-cli")),
        ffmpeg_path=str(settings.get("ffmpeg_path", "ffmpeg")),
    )


def validate_voice_config(config: VoiceConfig) -> None:
    if config.engine.lower() not in {"f5-tts", "f5", "f5tts"}:
        raise ConfigError(f"Unsupported voice engine: {config.engine}")
    if not config.reference_audio.exists():
        raise FileNotFoundError(f"Cloned voice reference audio not found: {config.reference_audio}")
    if not config.reference_text.exists():
        raise FileNotFoundError(f"Cloned voice reference text not found: {config.reference_text}")
    if config.sample_rate < 8000:
        raise ConfigError("voice.sample_rate must be at least 8000")
    if config.channels not in {1, 2}:
        raise ConfigError("voice.channels must be 1 or 2")


def load_scripts(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Scripts input file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Scripts input must be a JSON array")
    if not data:
        raise ValueError("Scripts input is empty")
    for index, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Script #{index} must be a JSON object")
        if not str(item.get("id", "")).strip():
            raise ValueError(f"Script #{index} is missing a non-empty id")
        if not str(item.get("script", "")).strip():
            raise ValueError(f"Script #{index} is missing non-empty script text")
    return data


def safe_job_id(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip())
    return cleaned.strip("-")[:80] or "voice-job"


def run_command(command: list[str], logger: Any, label: str) -> None:
    logger.info("%s command=%s", label, " ".join(shlex.quote(part) for part in command))
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Executable not found while running {label}: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or f"exit code {exc.returncode}"
        raise RuntimeError(f"{label} failed: {detail}") from exc
    if completed.stderr:
        logger.debug("%s stderr=%s", label, completed.stderr.strip())


def build_f5_command(script_text: str, raw_output: Path, config: VoiceConfig) -> list[str]:
    command = [
        config.f5_command,
        "--ref_audio",
        str(config.reference_audio),
        "--ref_text",
        config.reference_text.read_text(encoding="utf-8").strip(),
        "--gen_text",
        script_text,
        "--output_file",
        str(raw_output),
    ]
    return command


def build_normalize_command(raw_input: Path, final_output: Path, config: VoiceConfig) -> list[str]:
    return [
        config.ffmpeg_path,
        "-y",
        "-i",
        str(raw_input),
        "-af",
        f"loudnorm=I={config.normalize_lufs}:TP=-1.5:LRA=11",
        "-ar",
        str(config.sample_rate),
        "-ac",
        str(config.channels),
        str(final_output),
    ]


def synthesize_script(record: dict[str, Any], config: VoiceConfig, logger: Any, overwrite: bool = False) -> Path:
    job_id = safe_job_id(str(record["id"]))
    final_output = config.output_dir / f"{job_id}.wav"
    raw_output = config.temp_dir / f"{job_id}_f5_raw.wav"
    if final_output.exists() and not overwrite:
        logger.info("voice_exists job_id=%s path=%s", job_id, final_output)
        return final_output
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.temp_dir.mkdir(parents=True, exist_ok=True)
    script_text = str(record["script"]).strip()
    run_command(build_f5_command(script_text, raw_output, config), logger, "f5_tts")
    if not raw_output.exists():
        raise RuntimeError(f"F5-TTS completed but did not create expected WAV: {raw_output}")
    run_command(build_normalize_command(raw_output, final_output, config), logger, "ffmpeg_loudnorm")
    if not final_output.exists():
        raise RuntimeError(f"FFmpeg completed but did not create expected WAV: {final_output}")
    write_event("voice_generated", {"job_id": job_id, "path": str(final_output), "source_script_id": record.get("id")})
    logger.info("voice_generated job_id=%s path=%s", job_id, final_output)
    return final_output


def synthesize(script_text: str, job_id: str, output: str | None = None, config_path: str = "config/settings.json", overwrite: bool = True) -> Path:
    settings = load_settings(config_path)
    cfg = load_voice_config(settings, output_dir_override=str(Path(output).parent) if output else None)
    validate_voice_config(cfg)
    record = {"id": job_id, "script": script_text}
    logger = get_logger("voice")
    path = synthesize_script(record, cfg, logger, overwrite=overwrite)
    if output and path != Path(output):
        target = settings.resolve_path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        path.replace(target)
        return target
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate normalized WAV voiceovers for every script package using F5-TTS cloned voice settings.")
    parser.add_argument("--config", default="config/settings.json", help="Path to settings.json")
    parser.add_argument("--input", default=None, help="Input scripts JSON file, defaults to voice.input_file or output/scripts.json")
    parser.add_argument("--output-dir", default=None, help="Directory for generated WAV files, defaults to voice.output_dir or audio/")
    parser.add_argument("--limit", type=int, default=None, help="Optional maximum number of scripts to synthesize")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate WAV files even if they already exist")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
        logger = get_logger("voice")
        config = load_voice_config(settings, args.input, args.output_dir)
        validate_voice_config(config)
        scripts = load_scripts(config.input_file)
        if args.limit is not None:
            if args.limit < 1:
                raise ValueError("--limit must be greater than zero")
            scripts = scripts[: args.limit]
        outputs = [str(synthesize_script(record, config, logger, overwrite=args.overwrite)) for record in scripts]
        manifest = config.output_dir / "manifest.json"
        manifest.write_text(json.dumps({"count": len(outputs), "files": outputs}, indent=2), encoding="utf-8")
        write_event("voice_batch_generated", {"count": len(outputs), "manifest": str(manifest)})
        print(json.dumps({"count": len(outputs), "files": outputs, "manifest": str(manifest)}, indent=2))
        return 0
    except (ConfigError, FileNotFoundError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"voice failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
