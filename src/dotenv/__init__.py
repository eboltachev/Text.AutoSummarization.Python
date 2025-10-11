from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional


def load_dotenv(dotenv_path: Optional[str] = None) -> bool:
    path = Path(dotenv_path or ".env")
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"')
        os.environ.setdefault(key, value)
    return True
