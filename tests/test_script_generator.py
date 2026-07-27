from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from config import load_settings
from script_generator import load_json_array, local_script, main, script_spec, validate_script


def write_settings(tmp_path: Path) -> Path:
    settings = {
        "folders": {"output": "output", "logs": "logs", "state": "state", "prompts": "prompts"},
        "logging": {"file": "logs/factory.log", "level": "INFO"},
        "gemini": {"api_key_env": "MISSING_TEST_GEMINI_KEY"},
        "script_generation": {
            "topics_file": "output/topics.json",
            "output_file": "output/scripts.json",
            "prompt_file": "prompts/script_prompt.txt",
            "target_seconds": 40,
            "words_per_minute": 155,
            "max_title_chars": 60,
            "default_cta": "Follow for the next AI shortcut.",
            "default_hashtags": ["#AI", "#Tech", "#Shorts"],
        },
    }
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(settings), encoding="utf-8")
    (tmp_path / "prompts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "prompts" / "script_prompt.txt").write_text("Return strict JSON.", encoding="utf-8")
    return path


def sample_topic() -> dict[str, object]:
    return {
        "id": "abc123",
        "title": "AI agents can now operate web browsers for office workflows",
        "source": "test",
        "url": "https://example.com/story",
        "keywords": ["AI agents", "browser", "automation"],
    }


def test_load_json_array_validates_shape(tmp_path: Path) -> None:
    path = tmp_path / "topics.json"
    path.write_text(json.dumps([sample_topic()]), encoding="utf-8")
    assert load_json_array(path)[0]["id"] == "abc123"
    path.write_text(json.dumps({"title": "not a list"}), encoding="utf-8")
    try:
        load_json_array(path)
    except ValueError as exc:
        assert "JSON array" in str(exc)
    else:
        raise AssertionError("load_json_array should reject non-array topic input")


def test_local_script_contains_required_fields_and_metadata(tmp_path: Path) -> None:
    settings = load_settings(write_settings(tmp_path))
    spec = script_spec(settings)
    record = validate_script(local_script(sample_topic(), spec), spec)
    assert record["id"] == "abc123"
    assert record["topic_id"] == "abc123"
    assert record["generation_method"] == "local_template"
    assert record["word_count"] >= 70
    assert len(record["visual_beats"]) == 5
    assert all(str(tag).startswith("#") for tag in record["hashtags"])


def test_main_writes_scripts_without_gemini(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MISSING_TEST_GEMINI_KEY", raising=False)
    settings_path = write_settings(tmp_path)
    topics_path = tmp_path / "output" / "topics.json"
    topics_path.parent.mkdir(parents=True, exist_ok=True)
    topics_path.write_text(json.dumps([sample_topic()]), encoding="utf-8")
    output_path = tmp_path / "output" / "scripts.json"
    assert main(["--config", str(settings_path), "--topics", str(topics_path), "--output", str(output_path)]) == 0
    scripts = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(scripts) == 1
    assert scripts[0]["title"].startswith("AI agents")
    assert scripts[0]["source"] == "test"
