#!/usr/bin/env python3
"""Import one synthetic test message into Gmail.

This checks that the refresh token in .env works and that the gmail.insert
scope allows users.messages.import, before the real importer exists. It
refreshes an access token, builds a small message, and uploads it through the
same endpoint and with the same labels the importer will use.

Usage:

    python3 tools/test_insert.py

.env is read from the repository root. Every run adds one more message to the
mailbox, and the printed labels show whether Gmail put it in INBOX or SPAM.
"""

import email.message
import email.policy
import email.utils
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
IMPORT_URL = "https://gmail.googleapis.com/upload/gmail/v1/users/me/messages/import?uploadType=multipart"


def read_env(path):
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def post(url, data, headers):
    request = urllib.request.Request(url, data, headers)
    try:
        with urllib.request.urlopen(request) as response:
            return json.load(response)
    except urllib.error.HTTPError as e:
        sys.exit(f"error: {url} returned {e.code} {e.read().decode(errors='replace')}")


def main():
    env = read_env(ENV_FILE)
    with open(ROOT / env["GOOGLE_CLIENT_SECRET_FILE"], encoding="utf-8") as f:
        client = json.load(f)["installed"]

    tokens = post(client["token_uri"], urllib.parse.urlencode({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": env["GOOGLE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode(), {"Content-Type": "application/x-www-form-urlencoded"})

    # Only this test builds a message. The importer uploads the bytes fetched
    # over POP3 as they are.
    message = email.message.EmailMessage()
    message["From"] = "pop3import <test@example.com>"
    message["To"] = "test@example.com"
    message["Subject"] = "pop3import test"
    message["Date"] = email.utils.formatdate(localtime=True)
    message["Message-ID"] = email.utils.make_msgid(domain="example.com")
    message.set_content("pop3import API test\n")
    raw = message.as_bytes(policy=email.policy.SMTP)

    # Labels can only be set in JSON metadata, so the upload is multipart. The
    # message still goes in its own part as raw bytes, not base64 inside JSON.
    boundary = secrets.token_hex(16)
    metadata = json.dumps({"labelIds": ["INBOX", "UNREAD"]})
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata}\r\n"
        f"--{boundary}\r\nContent-Type: message/rfc822\r\n\r\n"
    ).encode() + raw + f"\r\n--{boundary}--\r\n".encode()

    result = post(IMPORT_URL, body, {
        "Authorization": f"Bearer {tokens['access_token']}",
        "Content-Type": f"multipart/related; boundary={boundary}",
    })
    print(f"imported id={result['id']} labels={','.join(result.get('labelIds', []))}")


if __name__ == "__main__":
    main()
