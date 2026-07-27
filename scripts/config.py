from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(path):
        if Path(path).exists():
            for line in Path(path).read_text(encoding='utf-8').splitlines():
                if line.strip() and not line.lstrip().startswith('#') and '=' in line:
                    k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

class Settings:
    def __init__(self, data: dict[str, Any]):
        self.data=data
        self.root=ROOT
        for p in data.get('folders', {}).values():
            (ROOT / p).mkdir(parents=True, exist_ok=True)
    def get(self, path: str, default: Any=None) -> Any:
        cur: Any=self.data
        for part in path.split('.'):
            if not isinstance(cur, dict) or part not in cur: return default
            cur=cur[part]
        return cur
    def path(self, key: str) -> Path:
        return self.root / self.get(f'folders.{key}', key)
    def env(self, name: str, required: bool=False) -> str | None:
        val=os.getenv(name)
        if required and not val: raise RuntimeError(f'Missing required environment variable: {name}')
        return val

def load_settings(path: str | Path | None=None) -> Settings:
    p=Path(path) if path else ROOT/'config'/'settings.json'
    return Settings(json.loads(p.read_text(encoding='utf-8')))
