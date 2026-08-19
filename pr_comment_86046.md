## Review — request changes (superseded by #86034 for ddgs)

Thanks for the repro work — the diagnosis of the `primp` panic is spot on. But this PR should be **withdrawn** in favor of #86034. Three reasons:

### 1. Scope-bundling (blocking)
This PR carries `scripts/fix_termux_cryptography.sh` (a patchelf stopgap) alongside the ddgs fix. Cryptography is #85985's domain (distro-copy), and the patchelf approach *conflicts* with it — two merged implementations would fight over the same `.so`. One PR = one problem; drop the crypto script here.

### 2. Brittle ad-filter (real bug)
`_run_ddgs_requests_search` walks results with:
```python
start = html.rfind('class="result', 0, m.start())
window = html[start:m.end()]
if "result--ad" in window:
    continue
```
This assumes the container's class attribute *begins* with `class="result`. If DDG reorders attributes (e.g. `class="results_links result"`), `rfind` lands on the previous result's anchor — leaking sponsored links or dropping organic results. A per-result-container split is robust to attribute order:
```python
for block in re.split(r'<div class="result', html):
    if "result--ad" in block:
        continue
    # parse title/snippet/url from `block`
```

### 3. Test violates AGENTS.md (policy)
`test_worker_selects_requests_fallback_on_termux` opens `_search_worker.py` and asserts substrings (`"_run_ddgs_requests_search" in src`). AGENTS.md bans "never read source code in tests" — this test passes while the wiring is broken and fails on a harmless rename. Replace with a behavioral test: invoke the worker's `main()` under Termux env markers with the provider functions stubbed.

### Decision
#86034 uses a real stdlib `HTMLParser` (no brittle regex), keeps the scope to ddgs only, and ships 18 behavioral tests with endpoint E2E. **Close this PR; take #86034 + its polish.** The cryptography problem is already covered by #85985.
