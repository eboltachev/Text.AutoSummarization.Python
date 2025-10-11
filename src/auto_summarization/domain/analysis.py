from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AnalysisResult:
    entities: Dict[str, List[str]] = field(default_factory=dict)
    sentiments: Dict[str, object] = field(default_factory=dict)
    classifications: Dict[str, object] = field(default_factory=dict)
    short_summary: Optional[str] = None
    full_summary: Optional[str] = None
