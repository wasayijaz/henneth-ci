"""Shared normalization for checker comparisons of generated CI products."""
from __future__ import annotations

from typing import Any


def without_root_meta(value: Any) -> Any:
    """Return logical product content, excluding only the root integrity envelope."""
    if not isinstance(value, dict) or "_meta" not in value:
        return value
    logical = dict(value)
    logical.pop("_meta", None)
    return logical
