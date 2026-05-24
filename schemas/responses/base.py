"""Structured output validation with repair and retry caps."""

from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from schemas.responses import MAX_LLM_RETRIES, MAX_REPAIR_ATTEMPTS, MAX_STRUCTURED_RETRIES_GLOBAL

T = TypeVar("T", bound=BaseModel)

_retry_counters: dict[str, int] = {}


def _extract_json(text: str) -> dict | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def parse_structured_response(
    raw: str,
    model: type[T],
    correlation_id: str,
) -> T:
    """Validate LLM output with repair parser and global retry cap."""
    counter_key = correlation_id
    attempts = _retry_counters.get(counter_key, 0)

    last_error: Exception | None = None
    for repair_round in range(MAX_REPAIR_ATTEMPTS + MAX_LLM_RETRIES + 1):
        if attempts >= MAX_STRUCTURED_RETRIES_GLOBAL:
            raise ValueError(
                f"Max structured retries ({MAX_STRUCTURED_RETRIES_GLOBAL}) exceeded for {correlation_id}"
            )
        attempts += 1
        _retry_counters[counter_key] = attempts

        try:
            if repair_round == 0:
                return model.model_validate_json(raw)
            payload = _extract_json(raw)
            if payload is None:
                raise ValidationError.from_exception_data("repair", [])
            return model.model_validate(payload)
        except (ValidationError, ValueError) as exc:
            last_error = exc
            continue

    raise ValueError(f"Structured parse failed for {correlation_id}: {last_error}")


def reset_retry_counter(correlation_id: str) -> None:
    _retry_counters.pop(correlation_id, None)
