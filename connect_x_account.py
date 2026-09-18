#!/usr/bin/env python3
"""
One-time script to obtain X (Twitter) OAuth 2.0 tokens for a given account.

Run locally -- it opens a browser and listens on localhost, so it will not
work in Lambda or any headless environment.

Usage:
    python connect_x_account.py <account_label>

Example:
    python connect_x_account.py gap_pre_prod_1

Credentials are hard-coded in the CONFIG block below. Fill in CLIENT_ID and
CLIENT_SECRET from your X developer app before running.

Tokens are written to tokens/<account_label>.json.
Run once per account you want to connect; the app itself stays owned by
whichever account created it.

Requires Python 3.7+. No third-party packages.
"""

import base64
import hashlib
import http.server
import json
import pathlib
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

# --------------------------------------------------------------------------
# CONFIG -- fill these in
# --------------------------------------------------------------------------

CLIENT_ID = "OWdDRF9xZC1iYk1sS2NDdldFWnk6MTpjaQ"
CLIENT_SECRET = "CVDXWF56-fFypyTKz0mJFIoedeyvMwtAIxv37V8Aftkm0X5Lit"

# Must match a callback URI registered on your X app, exactly.
REDIRECT_URI = "http://localhost:3000/callback"

SCOPES = "tweet.read tweet.write users.read offline.access"

# --------------------------------------------------------------------------

AUTH_URL = "https://x.com/i/oauth2/authorize"
TOKEN_URL = "https://api.x.com/2/oauth2/token"
ME_URL = "https://api.x.com/2/users/me"

HERE = pathlib.Path(__file__).resolve().parent
TOKEN_DIR = HERE / "tokens"


def check_config():
    if not CLIENT_ID or CLIENT_ID.startswith("PUT_YOUR"):
        sys.exit("CLIENT_ID is not set. Edit the CONFIG block at the top of this file.")
    if not CLIENT_SECRET or CLIENT_SECRET.startswith("PUT_YOUR"):
        sys.exit("CLIENT_SECRET is not set. Edit the CONFIG block at the top of this file.")


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Catches the single redirect X sends back after the user authorizes."""

    result = {}

    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        CallbackHandler.result = urllib.parse.parse_qs(query)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h2>Done. You can close this tab.</h2>")

    def log_message(self, *args):
        pass  # keep the console quiet


def build_pkce():
    """A random secret plus its hash. Sending the hash up front and the secret
    at exchange time proves the same program started and finished the flow."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def post_form(url, fields):
    body = urllib.parse.urlencode(fields).encode()
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Authorization", f"Basic {basic}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"Token request failed ({e.code}):\n{e.read().decode()}")


def whoami(access_token):
    req = urllib.request.Request(ME_URL)
    req.add_header("Authorization", f"Bearer {access_token}")
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)["data"]["username"]


def main():
    if len(sys.argv) != 2:
        sys.exit("Usage: python connect_x_account.py <account_label>")
    label = sys.argv[1]

    check_config()

    parsed = urllib.parse.urlparse(REDIRECT_URI)
    host = parsed.hostname or "localhost"
    port = parsed.port or 80

    verifier, challenge = build_pkce()
    state = secrets.token_urlsafe(16)

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print()
    print(f"Connecting account: {label}")
    print()
    print("The consent screen must show the handle you are connecting, NOT the")
    print("account that owns the app. If your browser is signed in as the wrong")
    print("one, open a private window, sign in as the right account, and paste")
    print("this URL there:")
    print()
    print(url)
    print()

    webbrowser.open(url)
    print(f"Waiting for the redirect on {host}:{port} ...")
    http.server.HTTPServer((host, port), CallbackHandler).handle_request()

    result = CallbackHandler.result
    if "error" in result:
        sys.exit(f"X returned an error: {result}")
    if "code" not in result:
        sys.exit(f"No authorization code came back. Got: {result}")
    if result.get("state", [None])[0] != state:
        sys.exit("State mismatch -- aborting.")

    # The code expires in roughly 30 seconds, hence exchanging it immediately.
    tokens = post_form(
        TOKEN_URL,
        {
            "grant_type": "authorization_code",
            "code": result["code"][0],
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
    )

    username = whoami(tokens["access_token"])
    if username.lower() != label.lower():
        print()
        print(f"WARNING: you asked for '{label}' but authorized as '@{username}'.")
        print("Saving anyway, but check this is what you intended.")

    TOKEN_DIR.mkdir(exist_ok=True)
    out = TOKEN_DIR / f"{label}.json"
    payload = {
        "username": username,
        "refresh_token": tokens["refresh_token"],
        "scope": tokens.get("scope"),
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print()
    print(f"Authorized as: @{username}")
    print(f"Refresh token saved to: {out}")
    print()
    print("The access token is not saved -- it expires in 2 hours. Use the")
    print("refresh token to mint a new one whenever you need it, and remember")
    print("that each refresh returns a NEW refresh token replacing the old one.")


if __name__ == "__main__":
    main()
