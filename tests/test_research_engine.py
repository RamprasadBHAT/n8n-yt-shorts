from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from config import load_settings
from research_engine import TopicCandidate, clean_title, filter_and_rank, main


def write_settings(tmp_path: Path) -> Path:
    settings = {
        "videos_per_batch": 2,
        "folders": {"output": "output", "logs": "logs", "state": "state"},
        "logging": {"file": "logs/factory.log", "level": "INFO"},
        "dedupe": {"state_file": "state/used_topics.json", "similarity_threshold": 0.86},
        "research": {"output_file": "output/topics.json", "max_topic_age_days": 30, "banned_terms": ["banned"]},
    }
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(settings), encoding="utf-8")
    return path


def test_clean_title_removes_markup_and_extra_space() -> None:
    assert clean_title("  <b>AI</b>   agents launch  ") == "AI agents launch"


def test_filter_and_rank_dedupes_history_and_banned_terms(tmp_path: Path) -> None:
    settings_path = write_settings(tmp_path)
    settings = load_settings(settings_path)
    history_path = tmp_path / "state" / "used_topics.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps([{"title": "AI browser agents are here"}]), encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat()
    candidates = [
        TopicCandidate("AI browser agents are here now", "test", published_at=now, score=100),
        TopicCandidate("Banned gadget launches", "test", published_at=now, score=90),
        TopicCandidate("Open source robots learn household chores", "test", published_at=now, score=80),
        TopicCandidate("New battery material doubles EV range", "test", published_at=now, score=70),
    ]
    records = filter_and_rank(candidates, settings, 2)
    assert [r["title"] for r in records] == ["Open source robots learn household chores", "New battery material doubles EV range"]
    assert json.loads(history_path.read_text(encoding="utf-8"))[-1]["title"] == "New battery material doubles EV range"


def test_main_writes_topics_from_fallback_file(tmp_path: Path, monkeypatch) -> None:
    settings_path = write_settings(tmp_path)
    fallback = tmp_path / "seeds.txt"
    fallback.write_text("AI search changes\nrobot chefs arrive\n", encoding="utf-8")
    data = json.loads(settings_path.read_text(encoding="utf-8"))
    data["research"]["fallback_topics_file"] = str(fallback)
    data["research"]["rss_feeds"] = []
    settings_path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr("research_engine.collect_hacker_news", lambda timeout: [])
    monkeypatch.setattr("research_engine.collect_reddit", lambda subs, timeout: [])
    output = tmp_path / "topics.json"
    assert main(["--config", str(settings_path), "--limit", "2", "--output", str(output)]) == 0
    topics = json.loads(output.read_text(encoding="utf-8"))
    assert len(topics) == 2
    assert topics[0]["source"] == "fallback_seed"
