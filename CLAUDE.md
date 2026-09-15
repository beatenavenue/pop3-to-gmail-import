# CLAUDE.md

Guidance for Claude and other AI assistants working in this repository.

This file is committed so that work in progress can be picked up on another development host. Nothing in it is meant for other readers, and it will be removed once the tool is complete.

Claude's auto-memory stays on the machine where it was written, so do not rely on it to carry anything to a later session. Treat it as scoped to the current session, and record decisions, recommendations, and the state of the work in this file instead.

## Project

A small tool that fetches mail over POP3, discards messages matching a simple rule, and imports the rest into Gmail with `users.messages.import`. See [README.md](README.md) for the motivation and the reasoning behind each design decision. Treat those decisions as settled unless the user explicitly revisits them.

## Language

- Write all repository content in English. This covers documentation, code comments, identifiers, commit messages, and issue or pull request text.
- Talk to the user in their native language. For the maintainer this is Japanese. Do not switch the conversation to English just because the files are in English.

### Translations

Reader-facing documents may have a Japanese translation. These live in `docs` with a `.ja` suffix, such as `docs/README.ja.md` and `docs/SETUP.ja.md`, and they are the only files exempt from the English rule above. The English version is authoritative, and each translation says so at the top. When an English document changes, update its translation in the same commit or note that it is out of date.

A link whose purpose is to send the reader to another language is written in the language it points to, not in the language of the surrounding document. The English README therefore links to the translation as `[日本語の説明はこちら]`. This is deliberate. Do not rewrite these links in English.

### English style

The maintainer publishes this text under their own name, so it must not contain punctuation they would not use themselves.

- Do not use em dashes. Use two hyphens (--), a comma, or separate sentences instead.
- Do not use colons or semicolons inside running sentences. They are fine in standalone blocks such as list introductions, headings, and code.

## Secrets and personal data

This is a public repository. Never commit any of the following.

- Real POP3 host names, user names, or passwords
- OAuth client secrets (`client_secret*.json`)
- OAuth access tokens or refresh tokens
- Real email addresses, including the list address used by the filter
- Real email messages

Test fixtures must be synthetic. Real mail may contain personal data belonging to third parties. Use the reserved domains `example.com`, `example.net`, and `example.org` for addresses.

Provide `.example` files with placeholder values, and keep the real files listed in `.gitignore`. If you notice a secret or real message already staged or committed, stop and tell the user before doing anything else.

Write for anyone who might use the tool, with work or private mail, on any machine and on any schedule. Do not describe the maintainer's own deployment anywhere in the repository, such as the kind of machine they run it on or the times they run it. The motivation in README that helps a reader decide whether the tool fits them is the exception.

## Invariants

- Never delete a message from the POP3 server unless it was imported successfully or intentionally discarded by the filter.
- Pass the raw message bytes to Gmail unchanged. Do not parse and re-serialize a message before upload.
- Use `users.messages.import`. Do not use `users.messages.insert` or IMAP `APPEND`, since both skip spam classification.
- Exit with a non-zero status on any failure, so the caller can notify and retry.
- Run once and exit. An external scheduler starts the tool, so do not turn it into a daemon.

## Implementation

The language is Python 3. The standard library covers the whole job, meaning `poplib` for the fetch, `email` for the rule, and `urllib` for the HTTP calls. `email` is also forgiving of the malformed headers that spam tends to carry, which matters because every message has to be parsed well enough to evaluate the rule.

Mail is fetched by this tool itself, with `poplib` from the standard library. getmail6 was considered and rejected. It is a standalone program, not a library, so using it would mean running this tool as an external MDA, which adds a second process, a second configuration file, getmail's own state file, and an exit status as the only channel for reporting what happened. getmail6 is itself built on `poplib`, so going direct gives up none of the protocol handling.

Two things carry over from reading getmail6's source. Set `poplib._MAXLINE` to a large value, since the default of 2048 bytes makes retrieval fail on any message with a longer line, and real mail has them. Use `poplib.POP3_SSL` for port 995 and `poplib.POP3` with `stls()` for port 110.

Identify messages by `UIDL`, fetch with `RETR`, and delete with `DELE`. A `DELE` is only committed when the session ends with `QUIT`, so a session that dies in the middle leaves every message it had already imported on the server, which would import them again on the next run.

Import through the media upload endpoint, `/upload/gmail/v1/users/me/messages/import`, so the raw message is sent as is rather than base64-encoded inside JSON. Apply the `INBOX` and `UNREAD` labels. Parse a message only to evaluate the filter rule, never to rebuild what is uploaded.

The standard library is the whole dependency list. Do not add a package, and do not use `google-api-python-client`. What is needed is `email` for the rule and `urllib` for the token refresh and the upload.

The tool is started by an external scheduler such as cron, on whatever schedule the user chooses. Nothing in the tool may assume a fixed interval between runs.

A key missing from `.env` ends in a `KeyError` traceback, and that is accepted. Users start from a copy of `.env.example`, which has every key, so do not add a friendlier check.

Obtaining the refresh token is a separate one-off program. Keep it out of the import path, since the import path runs unattended and never needs a browser.

In names, "insert" refers to the Gmail API side, after the `gmail.insert` scope, and "import" is reserved for real mail fetched over POP3. This holds even though both call `users.messages.import`. `tools/test_insert.py` pushes a synthetic test message and is named that way on purpose, so do not rename it.

The code is split into two files, so that the rule can grow without touching the import path. `mail_import.py` is the entry point a scheduler starts, and it does the fetch, the import, and the deletion. `mail_filter.py` holds the rule as `should_discard(message)`, which receives an `email.message.EmailMessage` parsed from the raw bytes with `email.policy.default` and returns True to delete the message without importing it. Pulling fields such as the subject or attachment filenames out of the message belongs in `mail_filter.py` too, so a new condition never changes the call in `mail_import.py`.

A real rule names real addresses, so `mail_filter.py` is listed in `.gitignore`. The repository carries `mail_filter.example.py` instead, whose function always returns False. Carry `mail_filter.py` to another host by hand, the same way as `.env`.

If the rule raises, the message is neither imported nor deleted, the other messages are still processed, and the run exits non-zero. Importing when the rule is broken could store exactly what the rule exists to destroy.

Output names a message by its UIDL and never by anything taken from the message, such as its subject, its sender, or an exception message that might quote a header. The tool runs unattended and its output is kept in logs, which should only show what happened to which UIDL. `tools/show_info_from_uidl.py`, planned below, looks up the headers for a UIDL when someone needs them.

Imported and rejected messages are recorded in a state file. Its path is `STATE_FILE` in `.env`, and a relative path is resolved against the repository root. The file is plain text with one line per message, holding a status word, a space, and the UIDL, such as `imported 000001a2b3c4d5e6` or `rejected 000001a2b3c4d5e8`. RFC 1939 limits a UIDL to 1 to 70 characters from 0x21 to 0x7E, so it never contains a space. The file holds identifiers only. Messages discarded by the filter are not recorded, since evaluating the rule again gives the same result.

At startup, after `UIDL`, lines whose UIDL the server no longer lists are dropped, and the file is rewritten through a temporary file and `os.replace`. This also removes a line left unfinished by a crash. After a successful import, the line is appended and flushed with `fsync` before `DELE`. A message already recorded as imported is deleted without being imported again.

A message Gmail rejects permanently stays on the POP3 server, and the user resolves it with a regular POP3 client such as Thunderbird. It is recorded as rejected and skipped on later runs. Only the run that meets the rejection exits non-zero, since exiting non-zero on every run would notify on every run until the user deals with the message. Only HTTP 400 and 413 count as permanent, since they point at the message itself. Any other error, 401, 403, 429, 5xx, and network errors included, concerns the account or the service. It stops the run, `QUIT` commits the deletions made so far, and the remaining messages wait for the next run.

The following is still open. Ask the user instead of choosing.

- Which host the tool runs on. Do not write deployment files before this is settled. No recommendation has been given

### Planned `tools/show_info_from_uidl.py`

This tool is not written yet, on purpose. There is no rejected message to test it against yet.

It takes a UIDL as its argument and prints enough about the matching message on the POP3 server for the user to find it in a regular mail client.

- Read the POP3 settings from `.env`. No Gmail credentials are needed
- Find the message number with `UIDL`, its size with `LIST`, and its headers with `TOP <number> 0`, so the body is never downloaded
- Print Subject, From, To, Date, Message-ID, the timestamp of the topmost `Received` header, and the size. Date is set by the sender and can be wrong, especially on spam, while the topmost `Received` header shows when the server accepted the message
- Decode headers with `email.parser.BytesHeaderParser` and `email.policy.default`, and print a header raw when it cannot be decoded
- Write only to standard output, never to disk, and never send `RETR` or `DELE`
- Exit non-zero when the UIDL is not on the server or the session fails
- `TOP` is optional in RFC 1939. Check that the server supports it when the tool is written

POP3 servers usually lock the mailbox for the length of a session, so running this at the same time as a scheduled run makes one of the two fail to log in.

## Scope

Keep the project small. The goal is a minimal, readable reference, not a general-purpose importer. Established alternatives are listed in README.md. Ask the user before adding features, dependencies, or configuration beyond what the current task needs.

The two halves of this project are not held to the same standard. Fetching mail and putting it into Gmail is a commodity that many tools already implement, so that path stays as small as it can be, and anything the standard library already does is not reimplemented here. The rule that decides which messages are destroyed is specific to this project, and it is allowed to grow as the maintainer needs.

## Current state

As of 2026-09-15, the maintainer's `.env` holds working credentials and a refresh token. `tools/test_insert.py` put a test message into Gmail, and `tools/test_pop3.py` logged in to the POP3 mailbox, both successfully. `mail_import.py` and `mail_filter.example.py` are written and pass a check against a local fake POP3 server and a fake Gmail endpoint. On 2026-09-16 `mail_import.py` also imported mail successfully from a test POP3 mailbox, which is what the maintainer's `.env` points at for now. It has not run against the real mailbox yet. The maintainer's real rule in `mail_filter.py` is not written yet. README still says the implementation is not written, and running the tool is not documented yet. `tools/show_info_from_uidl.py` is planned but deliberately not written.
