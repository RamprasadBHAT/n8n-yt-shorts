from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    class fuzz:  # type: ignore[no-redef]
        @staticmethod
        def token_set_ratio(a: str, b: str) -> int:
            sa, sb = set(a.lower().split()), set(b.lower().split())
            return int(100 * len(sa & sb) / max(len(sa | sb), 1))

import requests
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

USER_AGENT = "AIShortsFactory/1.0 (+https://github.com/RamprasadBHAT/n8n-yt-shorts)"


@dataclass(frozen=True)
class TopicCandidate:
    title: str
    source: str
    url: str = ""
    published_at: str | None = None
    score: float = 0.0
    keywords: list[str] | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def clean_title(title: str) -> str:
    title = re.sub(r"<[^>]+>", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" -\t\r\n")
    return title


def request_text(url: str, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured trusted feeds
        return response.read().decode("utf-8", "ignore")


def collect_rss(url: str, source: str, timeout: int) -> list[TopicCandidate]:
    xml_text = request_text(url, timeout)
    root = ET.fromstring(xml_text)
    items: list[TopicCandidate] = []
    for item in root.findall(".//item")[:50]:
        title = clean_title(item.findtext("title", ""))
        if len(title) < 12:
            continue
        items.append(
            TopicCandidate(
                title=title,
                source=source,
                url=item.findtext("link", "") or "",
                published_at=(parse_datetime(item.findtext("pubDate")) or utc_now()).isoformat(),
                keywords=extract_keywords(title),
            )
        )
    return items


def collect_hacker_news(timeout: int) -> list[TopicCandidate]:
    url = "https://hn.algolia.com/api/v1/search?tags=front_page"
    data = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout).json()
    items: list[TopicCandidate] = []
    for hit in data.get("hits", [])[:50]:
        title = clean_title(hit.get("title") or hit.get("story_title") or "")
        if len(title) < 12:
            continue
        points = float(hit.get("points") or 0)
        items.append(TopicCandidate(title=title, source="hacker_news", url=hit.get("url") or "", published_at=hit.get("created_at"), score=points, keywords=extract_keywords(title)))
    return items


def collect_reddit(subreddits: Iterable[str], timeout: int) -> list[TopicCandidate]:
    items: list[TopicCandidate] = []
    for subreddit in subreddits:
        url = f"https://www.reddit.com/r/{urllib.parse.quote(subreddit)}/hot.json?limit=25"
        data = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout).json()
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            title = clean_title(post.get("title", ""))
            if len(title) < 12:
                continue
            created = datetime.fromtimestamp(float(post.get("created_utc", time.time())), timezone.utc)
            score = float(post.get("score") or 0) + float(post.get("num_comments") or 0) * 0.5
            items.append(TopicCandidate(title=title, source=f"reddit:{subreddit}", url="https://www.reddit.com" + post.get("permalink", ""), published_at=created.isoformat(), score=score, keywords=extract_keywords(title)))
    return items


def extract_keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}", text.lower())
    stop = {"the", "and", "for", "with", "from", "that", "this", "are", "you", "why", "how", "has", "after", "about"}
    unique = []
    for word in words:
        if word not in stop and word not in unique:
            unique.append(word)
    return unique[:8]


def load_history(settings: Settings) -> list[dict[str, Any]]:
    path = settings.resolve_path(settings.get("dedupe.state_file", "state/used_topics.json"))
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def save_history(settings: Settings, history: list[dict[str, Any]]) -> None:
    path = settings.resolve_path(settings.get("dedupe.state_file", "state/used_topics.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history[-1000:], indent=2, ensure_ascii=False), encoding="utf-8")


def collect_candidates(settings: Settings, logger: Any) -> list[TopicCandidate]:
    research = settings.get("research", {}) or {}
    timeout = int(research.get("request_timeout_seconds", 20))
    candidates: list[TopicCandidate] = []
    feeds = research.get("rss_feeds") or [
        {"name": "google_news_ai", "url": "https://news.google.com/rss/search?q=AI%20technology&hl=en-US&gl=US&ceid=US:en"},
        {"name": "hn_rss", "url": "https://hnrss.org/frontpage"},
    ]
    for feed in feeds:
        try:
            candidates.extend(collect_rss(feed["url"], feed.get("name", feed["url"]), timeout))
        except Exception as exc:  # keep other sources alive
            logger.warning("source_failed source=%s error=%s", feed.get("name", feed.get("url")), exc)
    try:
        candidates.extend(collect_hacker_news(timeout))
    except Exception as exc:
        logger.warning("source_failed source=hacker_news error=%s", exc)
    try:
        candidates.extend(collect_reddit(research.get("reddit_subreddits", ["technology", "artificial"]), timeout))
    except Exception as exc:
        logger.warning("source_failed source=reddit error=%s", exc)
    if not candidates:
        seed_path = settings.resolve_path(research.get("fallback_topics_file", "11_Config/topics.txt"))
        for line in seed_path.read_text(encoding="utf-8").splitlines() if seed_path.exists() else []:
            title = clean_title(line)
            if title:
                candidates.append(TopicCandidate(title=f"{title}: what creators need to know now", source="fallback_seed", published_at=utc_now().isoformat(), keywords=extract_keywords(title)))
    return candidates


def apply_gemini_ranking(candidates: list[TopicCandidate], settings: Settings, logger: Any) -> list[TopicCandidate]:
    if not settings.get("research.use_gemini_ranking", False):
        return candidates
    api_env = settings.get("gemini.api_key_env", "GEMINI_API_KEY")
    if not settings.env(api_env):
        logger.info("gemini_ranking_skipped reason=missing_api_key env=%s", api_env)
        return candidates
    try:
        from gemini_client import GeminiClient

        payload = [{"index": i, "title": c.title, "source": c.source, "score": c.score} for i, c in enumerate(candidates[:60])]
        prompt = (
            "Rank these candidate YouTube Shorts topics for freshness, broad appeal, educational value, "
            "and low duplication risk. Return JSON only as an array of indexes, best first.\n"
            + json.dumps(payload, ensure_ascii=False)
        )
        ranked_indexes = GeminiClient().generate_json(prompt, temperature=float(settings.get("research.gemini_temperature", 0.2)))
        ordered: list[TopicCandidate] = []
        if isinstance(ranked_indexes, list):
            for index in ranked_indexes:
                if isinstance(index, int) and 0 <= index < len(candidates) and candidates[index] not in ordered:
                    base = candidates[index]
                    ordered.append(TopicCandidate(**{**asdict(base), "score": base.score + 10000 - len(ordered)}))
        return ordered + [candidate for candidate in candidates if candidate not in ordered]
    except Exception as exc:
        logger.warning("gemini_ranking_failed error=%s", exc)
        return candidates


def filter_and_rank(candidates: list[TopicCandidate], settings: Settings, limit: int, logger: Any | None = None) -> list[dict[str, Any]]:
    max_age_days = int(settings.get("research.max_topic_age_days", 14))
    cutoff = utc_now() - timedelta(days=max_age_days)
    threshold = float(settings.get("dedupe.similarity_threshold", 0.86)) * 100
    history = load_history(settings)
    banned = [str(x).lower() for x in settings.get("research.banned_terms", [])]
    seen_titles = [h.get("title", "") for h in history]
    ranked_candidates = apply_gemini_ranking(candidates, settings, logger) if logger else candidates
    selected: list[TopicCandidate] = []
    for candidate in sorted(ranked_candidates, key=lambda c: c.score, reverse=True):
        published = parse_datetime(candidate.published_at)
        if published and published < cutoff:
            continue
        lower = candidate.title.lower()
        if any(term and term in lower for term in banned):
            continue
        comparison = [c.title for c in selected] + seen_titles
        if any(fuzz.token_set_ratio(candidate.title, other) >= threshold for other in comparison):
            continue
        selected.append(candidate)
        if len(selected) >= limit:
            break
    records = []
    for index, candidate in enumerate(selected, 1):
        digest = hashlib.sha1(candidate.title.lower().encode("utf-8")).hexdigest()[:12]
        records.append({"id": digest, "rank": index, "title": candidate.title, "angle": "Explain why this matters in under 40 seconds", "source": candidate.source, "url": candidate.url, "published_at": candidate.published_at, "score": candidate.score, "keywords": candidate.keywords or extract_keywords(candidate.title), "selected_at": utc_now().isoformat()})
    save_history(settings, history + records)
    return records


def write_topics(records: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect, dedupe, rank, and persist YouTube Shorts topic candidates.")
    parser.add_argument("--config", default="config/settings.json", help="Path to settings.json")
    parser.add_argument("--limit", type=int, default=None, help="Number of topics to save")
    parser.add_argument("--output", default=None, help="Output topics JSON path")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config)
        logger = get_logger("research_engine")
        limit = args.limit or int(settings.get("videos_per_batch", 10))
        if limit < 1:
            raise ValueError("--limit must be greater than zero")
        output = settings.resolve_path(args.output or settings.get("research.output_file", "output/topics.json"))
        candidates = collect_candidates(settings, logger)
        topics = filter_and_rank(candidates, settings, limit, logger)
        if not topics:
            raise RuntimeError("No eligible topics found after source collection and deduplication")
        write_topics(topics, output)
        write_event("topics_generated", {"count": len(topics), "output": str(output)})
        print(json.dumps(topics, indent=2, ensure_ascii=False))
        return 0
    except (ConfigError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"research_engine failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
