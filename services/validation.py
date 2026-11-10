"""Shared validation helpers for AIS table imports and exports."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any


def normalize_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())


def formula_like(value: Any) -> bool:
    text = str(value).lstrip()
    return bool(text) and (
        text[0] in "=+@"
        or (text[0] == "-" and not re.fullmatch(r"-\d+(?:\.\d+)?", text))
    )


def duplicate_headers(headers: list[str]) -> list[str]:
    counts = Counter(normalize_header(header) for header in headers)
    return sorted({header for header in headers if counts[normalize_header(header)] > 1})
