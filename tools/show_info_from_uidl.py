#!/usr/bin/env python3
"""Print enough about one message on the POP3 server to find it in a mail client.

mail_import.py names a message only by its UIDL, for example when Gmail rejects
it or when the filter raises on it. This tool looks that UIDL up on the POP3
server and prints the subject, the addresses, the dates, the number of
attachments, and the size. That is enough to pick the message out in a regular
POP3 client such as Thunderbird and deal with it there.

Usage:

    python3 tools/show_info_from_uidl.py UIDL

.env is read from the repository root, and only the POP3 settings are used.
The whole message is retrieved with RETR, since counting attachments needs the
body. Nothing is written to disk and no message is ever deleted.

POP3 servers usually lock the mailbox during a session, so a login can fail
while mail_import.py or another client is connected to the same mailbox.
"""

import email.parser
import email.policy
import poplib
import ssl
import sys
import unicodedata
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
TIMEOUT = 60

# The default of 2048 bytes makes RETR fail on any message with a longer line,
# and real mail has them.
poplib._MAXLINE = 64 * 1024 * 1024


def read_env(path):
    env = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


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


def header_values(message, name):
    values = []
    for key, raw in message.raw_items():
        if key.lower() != name.lower():
            continue
        try:
            values.append(str(message.policy.header_fetch_parse(key, raw)))
        except Exception:
            # A header that cannot be decoded is shown as it came, unfolded.
            values.append(raw.replace("\r", "").replace("\n", ""))
    return values


def count_attachments(message):
    # A part counts when it has a filename, the same test as the example rule
    # in mail_filter.example.py. Inline images in signatures count too.
    return sum(1 for part in message.walk() if part.get_filename())


def printable(text):
    # Header bytes outside ASCII come back as surrogate escapes. Most such mail
    # is UTF-8, so they are decoded as UTF-8 and anything else is replaced.
    try:
        text = text.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
    except UnicodeEncodeError:
        text = text.encode("utf-8", "replace").decode("utf-8")
    # The sender wrote these headers, so control characters are escaped before
    # they reach the terminal.
    return "".join(
        f"\\x{ord(c):02x}" if unicodedata.category(c) == "Cc" and c != "\t" else c
        for c in text
    )


def main():
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} UIDL")
    uidl = sys.argv[1]
    env = read_env(ENV_FILE)

    try:
        pop = connect(env)
        numbers = {}
        for line in pop.uidl()[1]:
            number, _, listed = line.decode("ascii").partition(" ")
            numbers[listed] = number
        if uidl not in numbers:
            pop.quit()
            sys.exit(f"error: {uidl} is not on the server")
        # poplib strips the line endings and the dot-stuffing, so joining the
        # lines with CRLF gives back the bytes mail_import.py uploads.
        raw = b"\r\n".join(pop.retr(numbers[uidl])[1]) + b"\r\n"
        pop.quit()
    except (OSError, poplib.error_proto) as e:
        sys.exit(f"error: {e}")

    message = email.parser.BytesParser(policy=email.policy.default).parsebytes(raw)
    fields = []
    for name in ("Subject", "From", "To", "Cc", "Date"):
        fields += [(name, value) for value in header_values(message, name)] or [(name, "")]

    # The topmost Received header is the one added last, usually by the server
    # that holds the mailbox. Its date after the last semicolon tells when the
    # message arrived, while Date is set by the sender and can be wrong.
    received = header_values(message, "Received")
    fields.append(("Received", received[0].rpartition(";")[2].strip() if received else ""))
    fields += [("Message-ID", value) for value in header_values(message, "Message-ID")] or [("Message-ID", "")]

    try:
        attachments = str(count_attachments(message))
    except Exception:
        attachments = "unknown"
    fields.append(("Attachments", attachments))
    fields.append(("Size", f"{len(raw):,} bytes"))

    width = max(len(name) for name, _ in fields) + 1
    for name, value in fields:
        print(f"{name + ':':<{width}} {printable(value)}".rstrip())


if __name__ == "__main__":
    main()
