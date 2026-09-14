#!/usr/bin/env python3
"""Obtain a Google OAuth refresh token for pop3-to-gmail-import.

Run this once, on a machine with a web browser. It opens Google's consent
page, receives the authorization code on a loopback address, exchanges the
code for tokens, and prints the refresh token. Put that value in .env as
GOOGLE_REFRESH_TOKEN on the machine that runs the import.

Usage:

    python3 tools/get_google_refresh_token.py /path/to/client_secret.json

The client JSON is the one downloaded in step 4 of docs/SETUP.md. Authorize
with the Gmail account that will receive the imported mail.

This program is not part of the import path, which runs unattended and never
needs a browser.
"""

import base64
import hashlib
import http.server
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

SCOPE = "https://www.googleapis.com/auth/gmail.insert"


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} CLIENT_SECRET_FILE")

    with open(sys.argv[1], encoding="utf-8") as f:
        client_file = json.load(f)
    if "installed" not in client_file:
        sys.exit("error: not a Desktop app client file (no \"installed\" key)")
    client = client_file["installed"]

    # PKCE and state protect the code in transit to the loopback address.
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)

    params = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            if "code" not in query and "error" not in query:
                self.send_error(404)
                return
            params.update((key, values[0]) for key, values in query.items())
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Response received. Return to the terminal.\n")

        def log_message(self, format, *args):
            pass

    # Port 0 lets the OS pick a free port. Desktop app clients accept any
    # port on the loopback address.
    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}"

    auth_url = client["auth_uri"] + "?" + urllib.parse.urlencode({
        "client_id": client["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        # Both are needed for Google to return a refresh token every time.
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    print("Open this URL and authorize with the Gmail account that will receive the mail.", file=sys.stderr)
    print(auth_url, file=sys.stderr)
    webbrowser.open(auth_url)

    while not params:
        server.handle_request()
    server.server_close()

    if params.get("state") != state:
        sys.exit("error: state mismatch, the response does not belong to this request")
    if "error" in params:
        sys.exit(f"error: authorization failed: {params['error']}")

    body = urllib.parse.urlencode({
        "code": params["code"],
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }).encode()
    try:
        with urllib.request.urlopen(client["token_uri"], body) as response:
            tokens = json.load(response)
    except urllib.error.HTTPError as e:
        sys.exit(f"error: token request failed: {e.code} {e.read().decode(errors='replace')}")

    if SCOPE not in tokens.get("scope", "").split():
        sys.exit(f"error: {SCOPE} was not granted")
    if "refresh_token" not in tokens:
        sys.exit("error: the response has no refresh token")

    print("Set this as GOOGLE_REFRESH_TOKEN in .env.", file=sys.stderr)
    print(tokens["refresh_token"])


if __name__ == "__main__":
    main()
