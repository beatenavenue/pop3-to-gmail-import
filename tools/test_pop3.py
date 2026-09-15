#!/usr/bin/env python3
"""Log in to the POP3 mailbox in .env and print how many messages it holds.

This checks the POP3 settings in .env before the real importer exists. It
connects with TLS the same way the importer will, logs in, and reads the
message count with STAT. It never retrieves or deletes a message.

Usage:

    python3 tools/test_pop3.py

.env is read from the repository root. POP3 servers usually lock the mailbox
during a session, so a login can fail while another client, such as Gmail's own
POP3 fetch, is connected to the same mailbox.
"""

import poplib
import ssl
import sys
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
TIMEOUT = 30


def read_env(path):
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def main():
    env = read_env(ENV_FILE)
    host = env["POP3_HOST"]
    port = int(env["POP3_PORT"])
    tls = env["POP3_TLS"].lower()
    if tls not in ("true", "false"):
        sys.exit("error: POP3_TLS must be true or false")

    context = ssl.create_default_context()
    try:
        # POP3S speaks TLS from the start. Plain POP3 is upgraded with STLS
        # before the password is sent, and never runs without TLS.
        if tls == "true":
            pop = poplib.POP3_SSL(host, port, timeout=TIMEOUT, context=context)
        else:
            pop = poplib.POP3(host, port, timeout=TIMEOUT)
            pop.stls(context)
        pop.user(env["POP3_USER"])
        pop.pass_(env["POP3_PASSWORD"])
        count, _ = pop.stat()
        pop.quit()
    except (OSError, poplib.error_proto) as e:
        sys.exit(f"error: {host}:{port} {e}")
    print(f"connected messages={count}")


if __name__ == "__main__":
    main()
