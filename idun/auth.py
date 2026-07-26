"""Stdlib-only Entra device-code login for Idun (no azure.identity needed).

Flow: POST devicecode -> show user code -> poll token endpoint until granted
-> save FOUNDRY_TOKEN to ~/foundry_token.txt. Same endpoint/params the Azure
CLI uses, so it works headless on Termux.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Optional

TENANT = "885f01ab-7364-4484-be0a-231d541c9e7f"
SCOPE = "https://ai.azure.com/.default"
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"  # Azure CLI first-party app
TOKEN_FILE = os.path.join(os.path.expanduser("~"), "foundry_token.txt")
CODE_FILE = os.path.join(os.path.expanduser("~"), "foundry_code.txt")
AUTH_ENDPOINT = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0"


def _post(url: str, form: dict, headers=None) -> dict:
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def login() -> str:
    # 1) request device code
    dc = _post(f"{AUTH_ENDPOINT}/devicecode", {"client_id": CLIENT_ID, "scope": SCOPE})
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
            tok = _post(f"{AUTH_ENDPOINT}/token", form)
            if "access_token" in tok:
                token = tok["access_token"]
                with open(TOKEN_FILE, "w") as f:
                    f.write(token)
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


def load_token() -> Optional[str]:
    if os.path.exists(TOKEN_FILE):
        return open(TOKEN_FILE).read().strip()
    return None
