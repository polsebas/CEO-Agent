import json

import pytest
from pydantic import BaseModel

from schemas.responses.base import parse_structured_response, reset_retry_counter
from schemas.responses import MAX_STRUCTURED_RETRIES_GLOBAL, CEOResponse


class MiniModel(BaseModel):
    summary: str


def test_parse_valid_json():
    reset_retry_counter("c1")
    raw = json.dumps({"summary": "ok"})
    result = parse_structured_response(raw, MiniModel, "c1")
    assert result.summary == "ok"


def test_repair_partial_json():
    reset_retry_counter("c2")
    raw = 'Here is the result: {"summary": "repaired"}'
    result = parse_structured_response(raw, MiniModel, "c2")
    assert result.summary == "repaired"


def test_max_retries_enforced():
    reset_retry_counter("c3")
    with pytest.raises(ValueError, match="Max structured retries"):
        parse_structured_response("not json at all {{{", MiniModel, "c3")


def test_ceo_response_schema():
    r = CEOResponse(summary="test", priorities=["a"])
    assert r.summary == "test"
