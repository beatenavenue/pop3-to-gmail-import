#!/usr/bin/env python3
"""Import mail from a POP3 mailbox into Gmail, deleting what mail_filter.py discards.

Usage:

    python3 mail_import.py

.env and mail_filter.py are read from the directory this file is in. The tool
runs once and exits, so a scheduler such as cron starts it. Every message it
fetches is either discarded by the rule in mail_filter.py or imported into
Gmail with the INBOX and UNREAD labels, and is then deleted from the server.
A run handles at most MAX_MESSAGES_PER_RUN messages, and the rest wait for the
next run. A message that could not be handled stays on the server, and the
tool exits with a non-zero status.

Output names a message by its UIDL only. Nothing taken from a message, such as
its subject or sender, is printed, since the output usually ends up in a log.
"""

import email.parser
import email.policy
import json
import os
import poplib
import secrets
import ssl
import sys
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import mail_filter
except ModuleNotFoundError as e:
    if e.name != "mail_filter":
        raise
    sys.exit("error: mail_filter.py not found. Copy mail_filter.example.py to mail_filter.py.")

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
IMPORT_URL = "https://gmail.googleapis.com/upload/gmail/v1/users/me/messages/import?uploadType=multipart"
TIMEOUT = 60

# Statuses that point at the message itself, so sending it again would fail the
# same way. Every other error, 401 and 403 included, concerns the account or
# the service.
PERMANENT_STATUSES = {400, 413}

# The default of 2048 bytes makes RETR fail on any message with a longer line,
# and real mail has them.
poplib._MAXLINE = 64 * 1024 * 1024


class Rejected(Exception):
    pass


def read_env(path):
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def read_state(path):
    state = {}
    if path.exists():
        for line in path.read_text(encoding="ascii").splitlines():
            status, _, uidl = line.partition(" ")
            if status in ("imported", "rejected") and uidl and " " not in uidl:
                state[uidl] = status
    return state


def write_state(path, state):
    # Replacing the file in one step means a crash leaves either the old or the
    # new version, never a truncated one.
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="ascii") as f:
        f.writelines(f"{status} {uidl}\n" for uidl, status in state.items())
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def append_state(path, status, uidl):
    with open(path, "a", encoding="ascii") as f:
        f.write(f"{status} {uidl}\n")
        f.flush()
        os.fsync(f.fileno())


def refresh_access_token(env):
    with open(ROOT / env["GOOGLE_CLIENT_SECRET_FILE"], encoding="utf-8") as f:
        client = json.load(f)["installed"]
    data = urllib.parse.urlencode({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": env["GOOGLE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    request = urllib.request.Request(client["token_uri"], data, {"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.load(response)["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit(f"error: token refresh returned {e.code} {e.read().decode(errors='replace')}")
    except OSError as e:
        sys.exit(f"error: token refresh failed, {e}")


def connect(env):
    host = env["POP3_HOST"]
    port = int(env["POP3_PORT"])
    tls = env["POP3_TLS"].lower()
    if tls not in ("true", "false"):
        sys.exit("error: POP3_TLS must be true or false")

    context = ssl.create_default_context()
    # POP3S speaks TLS from the start. Plain POP3 is upgraded with STLS before
    # the password is sent, and never runs without TLS.
    if tls == "true":
        pop = poplib.POP3_SSL(host, port, timeout=TIMEOUT, context=context)
    else:
        pop = poplib.POP3(host, port, timeout=TIMEOUT)
        pop.stls(context)
    pop.user(env["POP3_USER"])
    pop.pass_(env["POP3_PASSWORD"])
    return pop


def import_message(access_token, raw):
    # Labels can only be set in JSON metadata, so the upload is multipart. The
    # message still goes in its own part as raw bytes, not base64 inside JSON.
    boundary = secrets.token_hex(16)
    metadata = json.dumps({"labelIds": ["INBOX", "UNREAD"]})
    body = (
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{metadata}\r\n"
        f"--{boundary}\r\nContent-Type: message/rfc822\r\n\r\n"
    ).encode() + raw + f"\r\n--{boundary}--\r\n".encode()

    request = urllib.request.Request(IMPORT_URL, body, {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": f"multipart/related; boundary={boundary}",
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            response.read()
    except urllib.error.HTTPError as e:
        if e.code in PERMANENT_STATUSES:
            raise Rejected(f"HTTP {e.code}") from None
        raise


def describe_filter_error(error):
    # The exception message is left out, since it may quote a header.
    frames = [f for f in traceback.extract_tb(error.__traceback__) if Path(f.filename).name == "mail_filter.py"]
    where = f" at mail_filter.py line {frames[-1].lineno}" if frames else ""
    return f"{type(error).__name__}{where}"


def main():
    env = read_env(ENV_FILE)
    state_file = ROOT / env["STATE_FILE"]
    limit = int(env["MAX_MESSAGES_PER_RUN"])
    access_token = refresh_access_token(env)
    counts = {"imported": 0, "discarded": 0, "rejected": 0, "skipped": 0, "deferred": 0}
    failed = False

    try:
        pop = connect(env)
        listing = [line.decode("ascii").split(" ", 1) for line in pop.uidl()[1]]

        # Forget messages that are no longer on the server. Rewriting the file
        # also drops a line that a crash may have left unfinished.
        on_server = {uidl for _, uidl in listing}
        state = {uidl: status for uidl, status in read_state(state_file).items() if uidl in on_server}
        write_state(state_file, state)

        # A busy mailbox holds more than one run can get through, so a run takes
        # the first MAX_MESSAGES_PER_RUN entries and leaves the rest. UIDL lists
        # messages in arrival order, so the oldest are handled first. The state
        # file is still pruned against the whole listing above, since a message
        # this run never reaches is still on the server.
        counts["deferred"] = max(len(listing) - limit, 0)

        for number, uidl in listing[:limit]:
            if state.get(uidl) == "rejected":
                counts["skipped"] += 1
                continue
            if state.get(uidl) == "imported":
                # Imported by an earlier session that ended before QUIT could
                # commit its DELE.
                pop.dele(number)
                continue

            # poplib strips the line endings and the dot-stuffing, so joining
            # the lines with CRLF gives back the message without POP3 framing.
            raw = b"\r\n".join(pop.retr(number)[1]) + b"\r\n"

            try:
                message = email.parser.BytesParser(policy=email.policy.default).parsebytes(raw)
                discard = mail_filter.should_discard(message)
            except Exception as e:
                print(f"error: {uidl} filter raised {describe_filter_error(e)}", file=sys.stderr)
                failed = True
                continue
            if discard:
                pop.dele(number)
                counts["discarded"] += 1
                continue

            try:
                import_message(access_token, raw)
            except Rejected as e:
                append_state(state_file, "rejected", uidl)
                print(f"error: {uidl} rejected by Gmail with {e}", file=sys.stderr)
                counts["rejected"] += 1
                failed = True
                continue
            except OSError as e:
                # The account or the service is at fault, so the remaining
                # messages would fail too. They wait for the next run.
                print(f"error: {uidl} import failed, {e}", file=sys.stderr)
                failed = True
                break
            append_state(state_file, "imported", uidl)
            pop.dele(number)
            counts["imported"] += 1

        pop.quit()
    except (OSError, poplib.error_proto) as e:
        sys.exit(f"error: {e}")

    print(" ".join(f"{name}={count}" for name, count in counts.items()))
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
