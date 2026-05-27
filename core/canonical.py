"""Stable canonical serialization for hashes, replay, and bindings."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

VOLATILE_KEYS = frozenset(
    {
        "timestamp",
        "created_at",
        "updated_at",
        "approved_at",
        "iat",
        "exp",
        "latency_ms",
    }
)


def _normalize(value: Any, *, strip_volatile: bool) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {
            str(k): _normalize(v, strip_volatile=strip_volatile)
            for k, v in sorted(value.items(), key=lambda x: str(x[0]))
            if not (strip_volatile and str(k) in VOLATILE_KEYS)
        }
    if isinstance(value, (list, tuple)):
        return [_normalize(v, strip_volatile=strip_volatile) for v in value]
    if hasattr(value, "model_dump"):
        return _normalize(value.model_dump(mode="json"), strip_volatile=strip_volatile)
    return str(value)


def canonical_json(data: Any, *, strip_volatile: bool = True) -> str:
    """Stable JSON: sorted keys, normalized types, optional volatile field strip."""
    normalized = _normalize(data, strip_volatile=strip_volatile)
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(data: Any, *, strip_volatile: bool = True) -> str:
    return hashlib.sha256(canonical_json(data, strip_volatile=strip_volatile).encode()).hexdigest()
