from backend.scripts.load_mfl_html_normalized import _json_safe


def test_json_safe_replaces_nan_with_none():
    value = {
        "a": float("nan"),
        "b": [1, float("nan"), {"c": float("nan")}],
    }

    out = _json_safe(value)

    assert out["a"] is None
    assert out["b"][1] is None
    assert out["b"][2]["c"] is None
