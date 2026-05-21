import hashlib
import json
import os
from pathlib import Path

CACHE_DIR = Path(".cache")
USE_CACHE = os.getenv("NO_CACHE", "").lower() not in ("1", "true", "yes")


def _cache_path(category: str, key_str: str) -> Path:
    key = hashlib.md5(key_str.encode()).hexdigest()[:16]
    p = CACHE_DIR / category
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{key}.json"


def cache_get(category: str, key_str: str):
    if not USE_CACHE:
        return None
    p = _cache_path(category, key_str)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


def cache_set(category: str, key_str: str, value) -> None:
    p = _cache_path(category, key_str)
    p.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
