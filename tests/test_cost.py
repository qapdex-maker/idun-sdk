"""Offline tests for cost accounting (idun.providers cost helpers)."""
from idun.providers import estimate_cost, cost_table


def test_cost_table_has_known_providers():
    tbl = cost_table()
    for pid in ("openai", "anthropic", "groq", "deepseek", "gemini", "xai",
                "perplexity", "fireworks", "novita"):
        assert pid in tbl, f"{pid} missing from cost table"
        assert "in" in tbl[pid] and "out" in tbl[pid]


def test_cost_table_omits_no_list_price():
    tbl = cost_table()
    # these have no public list price -> omitted (returns None from estimate)
    for pid in ("azure", "ollama", "local", "hf", "nous"):
        assert pid not in tbl


def test_estimate_cost_openai():
    # gpt-4o-mini: in $0.00015, out $0.00060 per 1K
    c = estimate_cost("openai", 1000, 1000)
    assert c is not None
    # 1K in * .00015 + 1K out * .00060 = .00075
    assert abs(c - 0.00075) < 1e-9


def test_estimate_cost_anthropic():
    c = estimate_cost("anthropic", 2000, 1000)
    # 2K*.003 + 1K*.015 = .006 + .015 = .021
    assert abs(c - 0.021) < 1e-9


def test_estimate_cost_no_list_price_is_none():
    assert estimate_cost("azure", 1000, 1000) is None
    assert estimate_cost("ollama", 1000, 1000) is None
    assert estimate_cost("nous", 1000, 1000) is None
    assert estimate_cost("hf", 1000, 1000) is None


def test_estimate_cost_zero_tokens_free():
    assert estimate_cost("gemini", 0, 0) == 0.0


def test_cost_table_returns_copy():
    tbl = cost_table()
    tbl["openai"]["in"] = 999
    assert cost_table()["openai"]["in"] != 999  # original untouched
