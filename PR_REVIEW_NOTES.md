# Hermes-Agent PR-Review — Termux-Fixes (#85985 / #86046 / #86034)

Decision (maßgebend, nach Sichtung aller 3 Diffs):

- **ddgs crash (#85972): MERGE #86034, CLOSE #86046.**
  - #86034 uses a real stdlib `HTMLParser` (`_DDGHTMLParser`) against the
    html.duckduckgo.com endpoint via `httpx` (already in venv). No new dep.
  - #86046 uses regex + `rfind('class="result', ...)` which breaks when DDG
    reorders attributes (`class="results_links result"`) — leaks ads / drops
    organic (Enough1122 #2, REAL bug). Also bundles `fix_termux_cryptography.sh`
    (Scope-Bundling, Enough1122 #4) and its test reads source (violates
    AGENTS.md "never read source in tests").
  - Action: withdraw #86046; take #86034 + apply the 3 minor polish fixes below.

- **cryptography crash (#83680): MERGE #85985** (distro-copy over PyPI overlay).
  - Beats #86046's patchelf stopgap (patchelf re-breaks on every `pip reinstall`).
  - Must fix the `.venv` silent-skip bug (below) before merge.

================================================================
PATCH 1 — #85985: fix `.venv` silent-skip (Enough1122 #1)
================================================================

File: hermes_cli/update_cmd.py (~line 996)

  # BEFORE (hardcoded "venv"):
  if _m()._is_termux_env():
      from hermes_cli.termux_crypto_fix import fix_termux_cryptography_overlay
      fix_termux_cryptography_overlay(_m().PROJECT_ROOT / "venv")

  # AFTER (derive the real venv from the running interpreter):
  if _m()._is_termux_env():
      from hermes_cli.termux_crypto_fix import fix_termux_cryptography_overlay
      import sys
      # hermes runs from inside its venv, so sys.prefix IS the venv root
      # (works for venv, .venv, or any custom name).
      fix_termux_cryptography_overlay(sys.prefix)

File: hermes_cli/termux_crypto_fix.py (~line 59)

  # BEFORE (silent skip when venv_py missing -> returns True = "fine"):
  def fix_termux_cryptography_overlay(venv_path):
      venv_path = str(venv_path)
      venv_py = os.path.join(venv_path, "bin", "python")
      if not os.path.isfile(venv_py):
          return True

  # AFTER (don't lie: if we can't find the interpreter, we can't assert OK):
  def fix_termux_cryptography_overlay(venv_path):
      venv_path = str(venv_path)
      venv_py = os.path.join(venv_path, "bin", "python")
      if not os.path.isfile(venv_py):
          # Can't verify; let the caller's import-check surface the problem
          # instead of silently claiming success.
          logger.warning("Termux crypto fix: venv python not found at %s", venv_py)
          return False

  # Durability follow-up (Enough1122 #2): after the copy, pin the distro
  # version so a later `pip install -U cryptography` can't silently re-overlay.
  # Add to the venv's constraints (or a post-install re-check hook in
  # hermes update). Minimal durable guard:
  #   write a constraints file disabling the PyPI wheel on Termux, e.g.
  #   echo "cryptography==$(python -c 'import cryptography;print(cryptography.__version__)')" \
  #        > "$venv_site/../termux-crypto-constraints.txt"
  # and reference it in install.sh's pip step. Track as follow-up; not blocking.

================================================================
PATCH 2 — #86034: 3 minor polish (Enough1122 review)
================================================================

File: plugins/web/ddgs/provider.py — `_run_ddg_html_search` / `search()`

  # Fix 1 (empty vs failure): distinguish "no results" from "parse/transport
  # failure" so the caller gets a clear error instead of empty success.
  results = _run_ddg_html_search(query, safe_limit)
  if not results:
      # could be a bot-challenge / 429 / markup change — surface, don't hide
      return {"success": False,
              "error": "DuckDuckGo HTML endpoint returned no parseable results "
                       "(possible bot-challenge or markup change)"}
  return {"success": True, "results": results, ...}

  # Fix 2 (interrupt parity): honor tools.interrupt like the ddgs path.
  from tools.interrupt import is_interrupted  # already imported elsewhere
  if is_interrupted():
      return {"success": False, "error": "search interrupted"}
  resp = httpx.post(..., timeout=10)
  if is_interrupted():
      return {"success": False, "error": "search interrupted"}

  # Fix 3 (uddg decode robustness): decode whenever the param is present,
  # not only on exact duckduckgo.com hosts.
  decoded = re.search(r"uddg=([^&]+)", href)
  if decoded:
      from urllib.parse import unquote
      url = unquote(decoded.group(1))

================================================================
ACTION SUMMARY FOR MAINTAINER
================================================================

1. Merge #85985 after applying PATCH 1 (`.venv` fix + durability follow-up).
2. Withdraw #86046 (superseded by #86034 for ddgs; its crypto .sh conflicts
   with #85985's distro-copy).
3. Merge #86034 after applying PATCH 2 (3 minor polish).
4. Update website/docs/getting-started/termux.md: document the distro-copy
   path as the truth; patchelf is only a stopgap (already noted in pyproject).

No write access to NousResearch/hermes-agent from this session — patches are
provided as copy-apply snippets above.
