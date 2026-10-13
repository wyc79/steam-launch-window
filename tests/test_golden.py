import json
import math

import pytest

from analysis import golden


@pytest.fixture(scope="module")
def built():
    return {name: json.loads(golden.dump(obj)) for name, obj in golden.build().items()}


def same(a, b) -> bool:
    """Equal, with floats to 12 digits: x ** 0.5 uses the C library's pow, which can
    differ in the last bit between the machine that wrote the files and CI."""
    if isinstance(a, float) or isinstance(b, float):
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isclose(a, b, rel_tol=1e-12)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def test_committed_golden_files_are_up_to_date(built):
    # site/test/golden.test.js reads these files; after a change to the reference, rerun python -m analysis.golden
    assert sorted(p.name for p in golden.OUT.glob("*.json")) == sorted(built)
    for name, obj in built.items():
        committed = json.loads((golden.OUT / name).read_text(encoding="utf-8"))
        assert same(committed, obj), f"{name} is out of date: run python -m analysis.golden"


def test_same_allows_only_the_last_digits():
    assert same({"a": [1, 0.1 + 0.2]}, {"a": [1, 0.3]})
    assert not same({"a": [1, 0.3]}, {"a": [1, 0.31]})
    assert not same([1], [1, 2]) and not same({"a": 1}, {"b": 1}) and not same(None, 0.0)
