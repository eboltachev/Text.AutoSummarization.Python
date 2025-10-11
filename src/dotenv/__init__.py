from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional


def _read_dotenv(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"')
        values[key] = value
    return values


def load_dotenv(dotenv_path: Optional[str] = None) -> bool:
    path = Path(dotenv_path or ".env")
    if not path.exists():
        return False
    for key, value in _read_dotenv(path).items():
        os.environ.setdefault(key, value)
    return True


def dotenv_values(dotenv_path: Optional[str] = None) -> Dict[str, str]:
    path = Path(dotenv_path or ".env")
    if not path.exists():
        return {}
    return _read_dotenv(path)


def find_dotenv(filename: str = ".env") -> str:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / filename
        if candidate.exists():
            return str(candidate)
    return ""


__all__ = ["load_dotenv", "dotenv_values", "find_dotenv"]
