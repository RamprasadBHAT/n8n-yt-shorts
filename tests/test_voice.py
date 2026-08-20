from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from config import load_settings
from voice import build_f5_command, build_normalize_command, load_scripts, load_voice_config, main, safe_job_id


def write_settings(tmp_path: Path) -> Path:
    (tmp_path / "assets" / "voice").mkdir(parents=True)
    (tmp_path / "assets" / "voice" / "reference.wav").write_bytes(b"RIFF")
    (tmp_path / "assets" / "voice" / "reference.txt").write_text("Reference voice text.", encoding="utf-8")
    settings = {
        "folders": {"audio": "audio", "logs": "logs", "temp": "temp", "output": "output"},
        "logging": {"file": "logs/factory.log", "level": "INFO"},
        "ffmpeg_path": "ffmpeg-test",
        "f5_tts": {"command": "f5-test"},
        "voice": {
            "engine": "f5-tts",
            "reference_audio": "assets/voice/reference.wav",
            "reference_text": "assets/voice/reference.txt",
            "speed": 1.1,
            "normalize_lufs": -16,
            "sample_rate": 48000,
            "channels": 2,
            "input_file": "output/scripts.json",
            "output_dir": "audio",
        },
    }
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(settings), encoding="utf-8")
    return path


def sample_scripts() -> list[dict[str, str]]:
    return [
        {"id": "script one", "script": "This is a complete voiceover script with enough text for synthesis."},
        {"id": "script/two", "script": "This is another complete voiceover script with enough text for synthesis."},
    ]


def test_load_scripts_validates_required_fields(tmp_path: Path) -> None:
    path = tmp_path / "scripts.json"
    path.write_text(json.dumps(sample_scripts()), encoding="utf-8")
    assert load_scripts(path)[0]["id"] == "script one"
    path.write_text(json.dumps([{"id": "missing text"}]), encoding="utf-8")
    try:
        load_scripts(path)
    except ValueError as exc:
        assert "script text" in str(exc)
    else:
        raise AssertionError("load_scripts should reject records without script text")


def test_build_commands_use_only_supported_f5_cli_arguments_and_normalization(tmp_path: Path) -> None:
    settings = load_settings(write_settings(tmp_path))
    cfg = load_voice_config(settings)
    f5 = build_f5_command("hello world", tmp_path / "raw.wav", cfg)
    assert f5[:5] == ["f5-test", "--ref_audio", str(cfg.reference_audio), "--ref_text", "Reference voice text."]
    assert "--speaker" not in f5
    assert "--speed" not in f5
    assert f5 == ["f5-test", "--ref_audio", str(cfg.reference_audio), "--ref_text", "Reference voice text.", "--gen_text", "hello world", "--output_file", str(tmp_path / "raw.wav")]
    ffmpeg = build_normalize_command(tmp_path / "raw.wav", tmp_path / "final.wav", cfg)
    assert ffmpeg[0] == "ffmpeg-test"
    assert "loudnorm=I=-16.0:TP=-1.5:LRA=11" in ffmpeg
    assert ffmpeg[-4:] == ["48000", "-ac", "2", str(tmp_path / "final.wav")]


def test_main_generates_batch_manifest_with_mocked_commands(tmp_path: Path, monkeypatch) -> None:
    settings_path = write_settings(tmp_path)
    scripts_path = tmp_path / "output" / "scripts.json"
    scripts_path.parent.mkdir(parents=True, exist_ok=True)
    scripts_path.write_text(json.dumps(sample_scripts()), encoding="utf-8")

    def fake_run(command, logger, label):
        output_path = Path(command[command.index("--output_file") + 1] if "--output_file" in command else command[-1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"RIFFfakewav")

    monkeypatch.setattr("voice.run_command", fake_run)
    assert main(["--config", str(settings_path), "--input", str(scripts_path), "--overwrite"]) == 0
    manifest = tmp_path / "audio" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["count"] == 2
    assert (tmp_path / "audio" / f"{safe_job_id('script one')}.wav").exists()
    assert (tmp_path / "audio" / f"{safe_job_id('script/two')}.wav").exists()


def test_cli_executes_fake_voice_generation_and_writes_audio(tmp_path: Path) -> None:
    settings_path = write_settings(tmp_path)
    f5 = tmp_path / "fake_f5.sh"
    f5.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "out=\"\"\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  case \"$1\" in\n"
        "    --output_file) out=\"$2\"; shift 2 ;;\n"
        "    --ref_audio|--ref_text|--gen_text) shift 2 ;;\n"
        "    --speaker) echo unsupported speaker >&2; exit 64 ;;\n"
        "    *) echo unsupported arg $1 >&2; exit 64 ;;\n"
        "  esac\n"
        "done\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "printf RIFFfake > \"$out\"\n",
        encoding="utf-8",
    )
    ffmpeg = tmp_path / "fake_ffmpeg.sh"
    ffmpeg.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "out=\"${@: -1}\"\n"
        "mkdir -p \"$(dirname \"$out\")\"\n"
        "printf RIFFnormalized > \"$out\"\n",
        encoding="utf-8",
    )
    f5.chmod(0o755)
    ffmpeg.chmod(0o755)
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    data["f5_tts"]["command"] = str(f5)
    data["ffmpeg_path"] = str(ffmpeg)
    settings_path.write_text(json.dumps(data), encoding="utf-8")
    scripts_path = tmp_path / "output" / "scripts.json"
    scripts_path.parent.mkdir(parents=True, exist_ok=True)
    scripts_path.write_text(json.dumps([sample_scripts()[0]]), encoding="utf-8")

    assert main(["--config", str(settings_path), "--input", str(scripts_path), "--overwrite"]) == 0
    output = tmp_path / "audio" / f"{safe_job_id('script one')}.wav"
    assert output.read_bytes() == b"RIFFnormalized"
