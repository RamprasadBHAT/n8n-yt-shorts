from __future__ import annotations

import argparse
import hashlib
import json
import re
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
class ScriptSpec:
    target_seconds: int
    words_per_minute: int
    max_title_chars: int
    hashtags: list[str]
    cta: str
    tone: str

    @property
    def target_words(self) -> int:
        return max(75, round(self.words_per_minute * self.target_seconds / 60))


def load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Input topics file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Topics input must be a JSON array")
    if not data:
        raise ValueError("Topics input is empty")
    for index, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Topic #{index} must be a JSON object")
        if not str(item.get("title", "")).strip():
            raise ValueError(f"Topic #{index} is missing a non-empty title")
    return data


def script_spec(settings: Settings) -> ScriptSpec:
    script_cfg = settings.get("script_generation", {}) or {}
    return ScriptSpec(
        target_seconds=int(script_cfg.get("target_seconds", settings.get("rendering.duration_seconds", 40))),
        words_per_minute=int(script_cfg.get("words_per_minute", 155)),
        max_title_chars=int(script_cfg.get("max_title_chars", 85)),
        hashtags=[str(tag) for tag in script_cfg.get("default_hashtags", ["#AI", "#Tech", "#Shorts"])],
        cta=str(script_cfg.get("default_cta", "Follow for the next AI shortcut.")),
        tone=str(script_cfg.get("tone", "punchy, factual, curious, and accessible")),
    )


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def trim_title(title: str, max_chars: int) -> str:
    clean = normalize_whitespace(title)
    if len(clean) <= max_chars:
        return clean
    trimmed = clean[: max_chars - 1].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{trimmed}…" if trimmed else clean[: max_chars - 1] + "…"


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def topic_keywords(topic: dict[str, Any]) -> list[str]:
    raw = topic.get("keywords") or []
    if isinstance(raw, str):
        raw = re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}", raw)
    keywords: list[str] = []
    for value in raw:
        text = normalize_whitespace(str(value)).lower()
        if text and text not in keywords:
            keywords.append(text)
    return keywords[:8]


def build_prompt(topic: dict[str, Any], spec: ScriptSpec, prompt_template: str) -> str:
    payload = {
        "topic": topic,
        "requirements": {
            "target_seconds": spec.target_seconds,
            "target_words": spec.target_words,
            "max_title_chars": spec.max_title_chars,
            "tone": spec.tone,
            "required_fields": ["title", "hook", "script", "description", "hashtags", "cta", "visual_beats"],
            "style": "No unsupported claims. No markdown. JSON object only. Write for spoken narration.",
        },
    }
    return f"{prompt_template.strip()}\n\n{json.dumps(payload, ensure_ascii=False, indent=2)}"


def local_script(topic: dict[str, Any], spec: ScriptSpec) -> dict[str, Any]:
    title = trim_title(str(topic["title"]), spec.max_title_chars)
    keywords = topic_keywords(topic)
    lead_keyword = keywords[0] if keywords else "this trend"
    hook = trim_title(f"{title} is moving faster than most people realize.", 115)
    script = (
        f"{hook} Here is the quick version. The headline is not just about {lead_keyword}; "
        "it is about how quickly tools, habits, and expectations are changing. First, watch who benefits: "
        "creators save time, teams automate repetitive work, and early adopters learn the new workflow before it feels normal. "
        "Second, watch the risk: every shortcut creates new mistakes, new policies, and new winners. "
        "The smart move is to test small, verify the facts, and build a repeatable system before the crowd catches up."
    )
    script = fit_script_length(script, spec.target_words)
    description = (
        f"{title}\n\n"
        f"A fast, practical breakdown of why this topic matters now and what to watch next. {spec.cta}\n\n"
        + " ".join(spec.hashtags)
    )
    return {
        "id": topic.get("id") or hashlib.sha1(title.lower().encode("utf-8")).hexdigest()[:12],
        "topic_id": topic.get("id"),
        "source_title": topic.get("title"),
        "title": title,
        "hook": hook,
        "script": script,
        "description": description,
        "cta": spec.cta,
        "hashtags": spec.hashtags,
        "visual_beats": visual_beats(title, keywords),
        "duration_seconds": spec.target_seconds,
        "word_count": word_count(script),
        "source": topic.get("source", "unknown"),
        "url": topic.get("url", ""),
        "generation_method": "local_template",
    }


def fit_script_length(script: str, target_words: int) -> str:
    words = script.split()
    min_words = max(70, target_words - 25)
    max_words = target_words + 20
    if len(words) > max_words:
        return " ".join(words[:max_words]).rstrip(" ,;:") + "."
    if len(words) < min_words:
        script += " Save this if you want a daily signal instead of another noisy headline."
    return script


def visual_beats(title: str, keywords: list[str]) -> list[dict[str, str]]:
    beats = [
        ("0-3", "Bold headline text over fast zoom on relevant stock footage", title),
        ("3-10", "Problem setup with highlighted keywords", ", ".join(keywords[:3]) or "trend context"),
        ("10-24", "Three quick proof points with kinetic captions", "who benefits, what changes, what to verify"),
        ("24-35", "Forward-looking implication with subtle push-in", "what happens next"),
        ("35-40", "CTA end card with channel branding", "follow for the next update"),
    ]
    return [{"time": time_range, "visual": visual, "caption_focus": focus} for time_range, visual, focus in beats]


def validate_script(record: dict[str, Any], spec: ScriptSpec) -> dict[str, Any]:
    required = ["title", "hook", "script", "description", "hashtags", "cta", "visual_beats"]
    for field in required:
        if field not in record:
            raise ValueError(f"Generated script missing required field: {field}")
    record["title"] = trim_title(record["title"], spec.max_title_chars)
    record["hook"] = normalize_whitespace(record["hook"])
    record["script"] = normalize_whitespace(record["script"])
    record["description"] = str(record["description"]).strip()
    if not isinstance(record["hashtags"], list) or not record["hashtags"]:
        record["hashtags"] = spec.hashtags
    record["hashtags"] = [tag if str(tag).startswith("#") else f"#{tag}" for tag in record["hashtags"]]
    if not isinstance(record["visual_beats"], list) or not record["visual_beats"]:
        record["visual_beats"] = visual_beats(record["title"], [])
    record["duration_seconds"] = int(record.get("duration_seconds") or spec.target_seconds)
    record["word_count"] = word_count(record["script"])
    if record["word_count"] < 50:
        raise ValueError("Generated narration is too short for a production Short")
    return record


def generate_with_gemini(topic: dict[str, Any], spec: ScriptSpec, settings: Settings, prompt_template: str) -> dict[str, Any] | None:
    api_env = settings.get("gemini.api_key_env", "GEMINI_API_KEY")
    if not settings.env(api_env):
        return None
    from gemini_client import GeminiClient

    generated = GeminiClient().generate_json(build_prompt(topic, spec, prompt_template), temperature=float(settings.get("script_generation.temperature", 0.7)))
    if not isinstance(generated, dict):
        raise ValueError("Gemini script response must be a JSON object")
    generated.setdefault("id", topic.get("id") or hashlib.sha1(str(topic["title"]).lower().encode("utf-8")).hexdigest()[:12])
    generated.setdefault("topic_id", topic.get("id"))
    generated.setdefault("source_title", topic.get("title"))
    generated.setdefault("source", topic.get("source", "unknown"))
    generated.setdefault("url", topic.get("url", ""))
    generated["generation_method"] = "gemini"
    return generated


def generate_scripts(topics: list[dict[str, Any]], settings: Settings, logger: Any) -> list[dict[str, Any]]:
    spec = script_spec(settings)
    prompt_path = settings.resolve_path(settings.get("script_generation.prompt_file", "prompts/script_prompt.txt"))
    prompt_template = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "Create a strict JSON YouTube Shorts script."
    scripts: list[dict[str, Any]] = []
    for topic in topics:
        try:
            record = generate_with_gemini(topic, spec, settings, prompt_template)
            if record is None:
                logger.info("gemini_script_skipped topic_id=%s reason=missing_api_key", topic.get("id"))
                record = local_script(topic, spec)
        except Exception as exc:
            logger.warning("gemini_script_failed topic_id=%s error=%s", topic.get("id"), exc)
            record = local_script(topic, spec)
        scripts.append(validate_script(record, spec))
    return scripts


def write_scripts(records: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate YouTube Shorts titles, hooks, scripts, descriptions, CTAs, hashtags, and visual beats from researched topics.")
    parser.add_argument("--config", default="config/settings.json", help="Path to settings.json")
    parser.add_argument("--topics", default=None, help="Input topics JSON file")
    parser.add_argument("--output", default=None, help="Output scripts JSON file")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
        logger = get_logger("script_generator")
        topics_path = settings.resolve_path(args.topics or settings.get("script_generation.topics_file", "output/topics.json"))
        output_path = settings.resolve_path(args.output or settings.get("script_generation.output_file", "output/scripts.json"))
        topics = load_json_array(topics_path)
        scripts = generate_scripts(topics, settings, logger)
        write_scripts(scripts, output_path)
        write_event("scripts_generated", {"count": len(scripts), "output": str(output_path)})
        print(json.dumps(scripts, indent=2, ensure_ascii=False))
        return 0
    except (ConfigError, FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"script_generator failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
