## Review — approve with minor polish

This is the right ddgs fix for Termux (beats #86046: real stdlib `HTMLParser` instead of brittle regex, ddgs-only scope, behavioral tests). Three small polish items before merge:

### 1. Empty vs failure (should fix)
When the parser yields zero results (bot-challenge, 429, or markup change), `search()` currently returns `success` with empty data. Callers can't tell "no hits" from "transport/parse failure". Distinguish:
```python
results = _run_ddg_html_search(query, safe_limit)
if not results:
    return {"success": False,
            "error": "DuckDuckGo HTML endpoint returned no parseable results "
                     "(possible bot-challenge or markup change)"}
```

### 2. Interrupt parity (nice to have)
`_run_ddg_html_search` does a single blocking `httpx.post` with no `tools.interrupt.is_interrupted()` check, while the ddgs path honors interrupts. The 10s timeout bounds it, but a Termux search can't be aborted early. Add a check before/after:
```python
from tools.interrupt import is_interrupted
if is_interrupted():
    return {"success": False, "error": "search interrupted"}
resp = httpx.post(..., timeout=10)
if is_interrupted():
    return {"success": False, "error": "search interrupted"}
```

### 3. `uddg` decode robustness (minor)
`_decode_ddg_url` only decodes `uddg` when the host is exactly `duckduckgo.com`/`www.duckduckgo.com`. Other DDG subdomains fall through and the user sees the redirect-wrapper URL. Decode whenever the param is present:
```python
decoded = re.search(r"uddg=([^&]+)", href)
if decoded:
    from urllib.parse import unquote
    url = unquote(decoded.group(1))
```

### Coordination
This PR is the chosen ddgs fix (per the #85972 triage). #86046 is being withdrawn in its favor, and #85985 owns the separate cryptography fix. After these 3 polish items, this is merge-ready.
