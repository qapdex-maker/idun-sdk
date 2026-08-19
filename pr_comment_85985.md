## Review — approve with required fixes

Solid fix. Distro-copy over the PyPI overlay is the right call (beats the patchelf stopgap in #86046, which re-breaks on every `pip reinstall`). The hazmat smoke-test is exactly the right gate. Two issues must be fixed before merge:

### 1. `.venv` silent-skip (blocking)
`update_cmd.py:996` hardcodes `PROJECT_ROOT / "venv"`. Anyone using `.venv` (or any custom name) hits `termux_crypto_fix.py:59`:
```python
if not os.path.isfile(venv_py):
    return True   # <- lies: claims success, applies no fix
```
The fix is silently skipped with no error. Derive the real venv from the running interpreter instead:

```python
# update_cmd.py
if _m()._is_termux_env():
    from hermes_cli.termux_crypto_fix import fix_termux_cryptography_overlay
    import sys
    # hermes runs from inside its venv, so sys.prefix IS the venv root
    # (works for venv, .venv, or any custom name).
    fix_termux_cryptography_overlay(sys.prefix)
```
And in `termux_crypto_fix.py`, stop lying when the interpreter isn't found:
```python
if not os.path.isfile(venv_py):
    logger.warning("Termux crypto fix: venv python not found at %s", venv_py)
    return False   # don't claim OK when we can't verify
```

### 2. Durability against `pip install -U cryptography` (follow-up)
After copying, pip's metadata still describes the PyPI wheel, so any later `pip install -U cryptography` (or dependency re-resolution) re-introduces the broken overlay. `hermes update` re-runs the fix, but a manual `pip -U` does not. Suggested durable guard: after the copy, pin the distro version in the venv's constraints so a reinstall can't re-overlay:
```python
# write $venv_site/../termux-crypto-constraints.txt
echo "cryptography==$(python -c 'import cryptography;print(cryptography.__version__)')"
```
and reference it in `install.sh`'s pip step. Not blocking, but track it.

### 3. POSIX layout (minor)
`venv_py = os.path.join(venv_path, "bin", "python")` assumes POSIX. Fine on Termux, but the helper is importable outside the `_is_termux_env()` guard — an `os.name == "posix"` early return would make it safe if ever reused elsewhere.

Net: fix #1, then this is merge-ready. (Coordinated with #86046/#86034 — see those threads: this PR owns cryptography, #86034 owns ddgs.)
