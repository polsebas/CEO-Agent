from core.canonical import stable_hash


def test_stable_hash_same_semantics_different_key_order():
    a = {"b": 2, "a": 1, "nested": {"z": 9, "y": 8}}
    b = {"a": 1, "b": 2, "nested": {"y": 8, "z": 9}}
    assert stable_hash(a) == stable_hash(b)


def test_stable_hash_strips_volatile_fields():
    a = {"action": "x", "created_at": "2020-01-01"}
    b = {"action": "x", "created_at": "2021-06-15"}
    assert stable_hash(a) == stable_hash(b)
