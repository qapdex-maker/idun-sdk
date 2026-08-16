"""Stdlib-only Entra device-code login for Idun (no azure.identity needed).

Flow: POST devicecode -> show user code -> poll token endpoint until granted
-> save FOUNDRY_TOKEN (+ expiry + refresh_token) to ~/foundry_token.txt.
Same endpoint/params the Azure CLI uses, so it works headless on Termux.

Phase 2.5: access tokens are short-lived. `maybe_refresh()` silently rotates
the token via the OAuth refresh_token grant before it expires (5-min slack),
and falls back to a fresh device-code login when no refresh token is stored.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional, Tuple

# No tenant is bundled: "organizations" is the multi-tenant Entra endpoint and
# works for any tenant. Override with IDUN_TENANT=<your-tenant-guid>.
TENANT_DEFAULT = "organizations"
SCOPE = "https://ai.azure.com/.default"
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"  # Azure CLI first-party app
TOKEN_FILE = os.path.join(os.path.expanduser("~"), "foundry_token.txt")
CODE_FILE = os.path.join(os.path.expanduser("~"), "foundry_code.txt")


def tenant() -> str:
    """Entra tenant from IDUN_TENANT (or AZURE_TENANT_ID), else multi-tenant."""
    return (os.environ.get("IDUN_TENANT")
            or os.environ.get("AZURE_TENANT_ID")
            or TENANT_DEFAULT).strip()


def auth_endpoint() -> str:
    """OAuth2 v2.0 endpoint for the configured tenant (resolved at call time)."""
    return f"https://login.microsoftonline.com/{tenant()}/oauth2/v2.0"


# Backwards-compatible aliases (no longer tenant-specific).
TENANT = TENANT_DEFAULT
AUTH_ENDPOINT = auth_endpoint()

# Refresh the token this many seconds before it actually expires.
REFRESH_SLACK = 300


def _post(url: str, form: dict, headers=None) -> dict:
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _save(token: str, expires_in: float, refresh_token: Optional[str] = None) -> None:
    """Persist token + metadata as JSON (expires_at epoch seconds)."""
    meta = {
        "access_token": token,
        "expires_at": time.time() + float(expires_in),
        "refresh_token": refresh_token,
    }
    tmp = TOKEN_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(meta, f)
    os.replace(tmp, TOKEN_FILE)  # atomic


def _load_meta() -> Optional[dict]:
    if not os.path.exists(TOKEN_FILE):
        return None
    try:
        with open(TOKEN_FILE) as f:
            meta = json.load(f)
        # tolerate legacy plain-token file
        if "access_token" not in meta and isinstance(meta, dict):
            return None
        return meta
    except (json.JSONDecodeError, ValueError):
        # legacy: file held a bare token string
        return None


def login() -> str:
    # 1) request device code
    dc = _post(f"{auth_endpoint()}/devicecode", {"client_id": CLIENT_ID, "scope": SCOPE})
    msg = (f"To sign in, use a web browser to open {dc['verification_uri']} "
           f"and enter the code {dc['user_code']} to authenticate.")
    with open(CODE_FILE, "w") as f:
        f.write(msg + "\n")
    print(msg, flush=True)
    print(f"(code also saved to {CODE_FILE})", flush=True)

    # 2) poll for token
    interval = int(dc.get("interval", 5))
    expires = time.time() + float(dc.get("expires_in", 900))
    form = {
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "client_id": CLIENT_ID,
        "device_code": dc["device_code"],
    }
    while time.time() < expires:
        try:
            tok = _post(f"{auth_endpoint()}/token", form)
            if "access_token" in tok:
                token = tok["access_token"]
                _save(token, tok.get("expires_in", 900), tok.get("refresh_token"))
                print(f"TOKEN_OK len={len(token)}")
                print(f"saved to {TOKEN_FILE}")
                return token
        except urllib.error.HTTPError as e:
            err = json.loads(e.read().decode("utf-8", "replace"))
            if err.get("error") == "authorization_pending":
                time.sleep(interval)
                continue
            if err.get("error") == "slow_down":
                interval += 5
                time.sleep(interval)
                continue
            raise RuntimeError(f"Login failed: {err.get('error_description', err)}")
    raise RuntimeError("Login timed out. Re-run `idun login`.")


def _refresh_with(refresh_token: str) -> Optional[Tuple[str, Optional[str]]]:
    """Try the refresh_token grant. Returns (new_token, new_refresh) or None."""
    form = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "scope": SCOPE,
        "refresh_token": refresh_token,
    }
    try:
        tok = _post(f"{auth_endpoint()}/token", form)
    except urllib.error.HTTPError:
        return None
    if "access_token" not in tok:
        return None
    new_refresh = tok.get("refresh_token", refresh_token)
    return tok["access_token"], new_refresh


def maybe_refresh(force: bool = False) -> Optional[str]:
    """Rotate the stored token if it is within REFRESH_SLACK of expiry.

    - returns the (possibly new) access token, or None if no token stored
    - with a stored refresh_token it uses the silent refresh grant
    - without one it triggers a fresh device-code login (interactive)
    - `force=True` always rotates regardless of remaining lifetime
    """
    meta = _load_meta()
    if meta is None:
        return None
    token = meta.get("access_token", "")
    expires_at = float(meta.get("expires_at", 0))
    refresh = meta.get("refresh_token")
    near_expiry = (expires_at - time.time()) <= REFRESH_SLACK

    if not force and not near_expiry and token:
        return token

    if refresh:
        got = _refresh_with(refresh)
        if got:
            new_token, new_refresh = got
            _save(new_token, 900, new_refresh)
            print(f"TOKEN_REFRESHED len={len(new_token)}", flush=True)
            return new_token
    # no refresh token (legacy) or refresh failed -> interactive re-login
    print("TOKEN_EXPIRED triggering device-code login", flush=True)
    return login()


def load_token() -> Optional[str]:
    """Return the access token, rotating it first if it is near expiry.

    Keeps the old `load_token()` contract (returns a str or None) while
    making callers immune to token expiry.
    """
    return maybe_refresh()
