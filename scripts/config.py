from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv(path: str | Path) -> None:
        p = Path(path)
        if not p.exists():
            return
        for line in p.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key, value = stripped.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


class ConfigError(ValueError):
    """Raised when settings.json is missing required production settings."""


@dataclass(frozen=True)
class Settings:
    data: dict[str, Any]
    root: Path = ROOT

    def __post_init__(self) -> None:
        folders = self.get("folders", {})
        if not isinstance(folders, dict) or not folders:
            raise ConfigError("settings.json must define a non-empty folders object")
        for folder in folders.values():
            if not isinstance(folder, str) or not folder.strip():
                raise ConfigError("all configured folder paths must be non-empty strings")
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def get(self, dotted_path: str, default: Any = None) -> Any:
        current: Any = self.data
        for part in dotted_path.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    def require(self, dotted_path: str) -> Any:
        value = self.get(dotted_path)
        if value is None or value == "":
            raise ConfigError(f"Missing required configuration: {dotted_path}")
        return value

    def path(self, folder_key: str, *parts: str) -> Path:
        folder = self.get(f"folders.{folder_key}", folder_key)
        return self.root.joinpath(folder, *parts)

    def resolve_path(self, configured_path: str | Path) -> Path:
        path = Path(configured_path)
        return path if path.is_absolute() else self.root / path

    def env(self, name: str, required: bool = False) -> str | None:
        value = os.getenv(name)
        if required and not value:
            raise ConfigError(f"Missing required environment variable: {name}")
        return value


def load_settings(path: str | Path | None = None) -> Settings:
    settings_path = Path(path) if path else ROOT / "config" / "settings.json"
    if not settings_path.exists():
        raise ConfigError(f"Settings file not found: {settings_path}")
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {settings_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError("settings.json must contain a JSON object")
    root = settings_path.parent.parent if settings_path.parent.name == "config" else settings_path.parent
    return Settings(data=data, root=root.resolve())
