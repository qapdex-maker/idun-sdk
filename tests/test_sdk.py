"""Tests for idun-sdk: normalization + CLI arg parsing (no network)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from idun.client import _normalize_output


def test_normalize_trajectory():
    sample = {
        "model": "gpt-5.4-2026-03-05",
        "output": [
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Plan: clarify Contoso."}]},
            {"type": "web_search_call", "status": "completed", "id": "ws_1",
             "action": {"type": "search", "queries": ["Contoso current CEO"], "query": "Contoso current CEO"}},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Final answer."}]},
        ],
    }
    res = _normalize_output(sample)
    assert res.model == "gpt-5.4-2026-03-05", res.model
    assert res.text == "Plan: clarify Contoso.\n\nFinal answer.", repr(res.text)
    assert len(res.steps) == 3, len(res.steps)
    assert res.steps[0].kind == "reasoning"
    assert res.steps[1].kind == "tool" and res.steps[1].tool == "web_search"
    assert res.steps[1].query == "Contoso current CEO" and res.steps[1].status == "completed"
    assert res.steps[2].kind == "reasoning"
    print("PASS test_normalize_trajectory")


def test_cli_help():
    import subprocess
    r = subprocess.run([sys.executable, "-m", "idun_cli", "--help"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and "trace" in r.stdout and "chat" in r.stdout, r.stdout
    print("PASS test_cli_help")


if __name__ == "__main__":
    test_normalize_trajectory()
    test_cli_help()
    print("\nALL TESTS PASS")
