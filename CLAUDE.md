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

This covers deployment files as well. A systemd unit, an installed crontab, a container image, or anything else carrying one host's paths, user names, and schedule belongs on that host, not here. Where a scheduler has to be shown, show it the way `tools/run_cron.sh` does, with paths derived from the location of the file and the interval left to the reader. Which host the maintainer runs the tool on is their own business and not a question for this repository.

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

A relative path in `.env` is resolved against the repository root, for `GOOGLE_CLIENT_SECRET_FILE` as well as `STATE_FILE`. A scheduler does not necessarily start the tool from there, so resolving against the current directory would break under cron. Joining the root with an absolute path leaves it unchanged, so the values SETUP asks for still work.

Obtaining the refresh token is a separate one-off program. Keep it out of the import path, since the import path runs unattended and never needs a browser.

In names, "insert" refers to the Gmail API side, after the `gmail.insert` scope, and "import" is reserved for real mail fetched over POP3. This holds even though both call `users.messages.import`. `tools/test_insert.py` pushes a synthetic test message and is named that way on purpose, so do not rename it.

The code is split into two files, so that the rule can grow without touching the import path. `mail_import.py` is the entry point a scheduler starts, and it does the fetch, the import, and the deletion. `mail_filter.py` holds the rule as `should_discard(message)`, which receives an `email.message.EmailMessage` parsed from the raw bytes with `email.policy.default` and returns True to delete the message without importing it. Pulling fields such as the subject or attachment filenames out of the message belongs in `mail_filter.py` too, so a new condition never changes the call in `mail_import.py`.

A real rule names real addresses, so `mail_filter.py` is listed in `.gitignore`. The repository carries `mail_filter.example.py` instead, whose function always returns False. Carry `mail_filter.py` to another host by hand, the same way as `.env`.

If the rule raises, the message is neither imported nor deleted, the other messages are still processed, and the run exits non-zero. Importing when the rule is broken could store exactly what the rule exists to destroy.

Output names a message by its UIDL and never by anything taken from the message, such as its subject, its sender, or an exception message that might quote a header. The tool runs unattended and its output is kept in logs, which should only show what happened to which UIDL. `tools/show_info_from_uidl.py`, described below, looks up a UIDL and prints what someone needs to find the message.

Imported and rejected messages are recorded in a state file. Its path is `STATE_FILE` in `.env`, and a relative path is resolved against the repository root. The file is plain text with one line per message, holding a status word, a space, and the UIDL, such as `imported 000001a2b3c4d5e6` or `rejected 000001a2b3c4d5e8`. RFC 1939 limits a UIDL to 1 to 70 characters from 0x21 to 0x7E, so it never contains a space. The file holds identifiers only. Messages discarded by the filter are not recorded, since evaluating the rule again gives the same result.

At startup, after `UIDL`, lines whose UIDL the server no longer lists are dropped, and the file is rewritten through a temporary file and `os.replace`. This also removes a line left unfinished by a crash. After a successful import, the line is appended and flushed with `fsync` before `DELE`. A message already recorded as imported is deleted without being imported again.

A run handles at most `MAX_MESSAGES_PER_RUN` entries from the `UIDL` listing, 200 in `.env.example`. A mailbox with a backlog would otherwise hold one long session open, with the mailbox locked against every other client, and an error late in that session leaves everything after it unhandled anyway. The default matches Gmail's own POP3 fetch, which retrieved at most 200 messages at a time.

The limit counts every entry in the listing, not only the messages that are retrieved. An entry the state file records as rejected uses a slot even though it costs no traffic. Counting only retrievals was considered and rejected, since the limit is easier to explain and to predict when it means the first N of the listing. The listing is in arrival order, so the oldest go first. The remainder is reported as `deferred` in the counts line, and reaching the limit is not a failure, so the run still exits 0. Watching that count is how a user notices that the schedule and the limit together are not keeping up.

The state file is pruned against the whole listing, never against the part a run handles, since a message the run does not reach is still on the server.

A message Gmail rejects permanently stays on the POP3 server, and the user resolves it with a regular POP3 client such as Thunderbird. It is recorded as rejected and skipped on later runs. Only the run that meets the rejection exits non-zero, since exiting non-zero on every run would notify on every run until the user deals with the message. Only HTTP 400 and 413 count as permanent, since they point at the message itself. Any other error, 401, 403, 429, 5xx, and network errors included, concerns the account or the service. It stops the run, `QUIT` commits the deletions made so far, and the remaining messages wait for the next run.

### `tools/show_info_from_uidl.py`

It takes a UIDL as its argument and prints enough about the matching message on the POP3 server for the user to find it in a regular mail client. It does not show the whole message. The user identifies the message from this output and does the rest in a client such as Thunderbird.

- Read the POP3 settings from `.env`. No Gmail credentials are needed
- Find the message number with `UIDL` and retrieve the whole message with `RETR`. The maintainer added attachments to the output on 2026-09-16, and telling whether a message has any needs the body, so headers alone from `TOP <number> 0` are not enough. `RETR` does not change the mailbox, and a message reported by `mail_import.py` has been retrieved once already
- Print Subject, From, To, Cc, Date, the date of the topmost `Received` header, Message-ID, the number of attachments, and the size. Date is set by the sender and can be wrong, especially on spam, while the topmost `Received` header shows when the server accepted the message
- Count a MIME part as an attachment when it has a filename, the same test as the example rule in `mail_filter.example.py`
- Give the size as the length of the retrieved bytes, which is what `mail_import.py` uploads
- Decode headers with `email.policy.default`, and print a header raw when it cannot be decoded. Escape control characters, since the sender wrote the headers and the output goes to a terminal
- Write only to standard output, never to disk, and never send `DELE`
- Exit non-zero when the UIDL is not on the server or the session fails

POP3 servers usually lock the mailbox for the length of a session, so running this at the same time as a scheduled run makes one of the two fail to log in.

### `tools/run_cron.sh`

A bash wrapper that cron starts in place of `mail_import.py`. It exists because the importer prints no dates and takes no lock, and both are wanted once an unattended scheduler runs it.

- Print the date and time on a `start` line before the run and on an `end` line after it, with `date +%Y-%m-%dT%H:%M:%S%z`. The end line also carries the importer's exit status and the elapsed seconds from `SECONDS`
- Hold a lock on `.cron.lock` in the repository root for the length of the run, through `flock -n` on file descriptor 9. The kernel releases it when the shell exits, so a run that is killed does not lock the next one out. `.cron.lock` is listed in `.gitignore`
- A run that cannot take the lock prints `not started, another run holds <path>` and exits 0. The maintainer chose this on 2026-09-19. One overlap is not a failure, and exiting non-zero would notify every time a run ran long. The cost is that a hung run holding the lock stops imports quietly, so the line is documented in `docs/USAGE.md` as something to watch
- Exit with the importer's own status in every other case, so the non-zero on failure invariant still reaches the caller
- Resolve the repository root from the path of the script, so cron can start it by its full path from any directory
- Stop with a non-zero status and a message if `flock` is missing, rather than running unlocked
- Write nothing to a log file of its own. cron mails what the job writes, and the comment at the top of the script shows the redirect for those who want a file instead

It was checked on 2026-09-19 against a stub `mail_import.py`, covering a normal run, a non-zero exit from the importer, an overlapping run, a run started from another directory, a run killed mid-session, and a cron like environment with an empty environment and a minimal PATH. It has not been registered in a real crontab.

## Scope

Keep the project small. The goal is a minimal, readable reference, not a general-purpose importer. Established alternatives are listed in README.md. Ask the user before adding features, dependencies, or configuration beyond what the current task needs.

The two halves of this project are not held to the same standard. Fetching mail and putting it into Gmail is a commodity that many tools already implement, so that path stays as small as it can be, and anything the standard library already does is not reimplemented here. The rule that decides which messages are destroyed is specific to this project, and it is allowed to grow as the maintainer needs.

## Current state

As of 2026-09-15, the maintainer's `.env` holds working credentials and a refresh token. `tools/test_insert.py` put a test message into Gmail, and `tools/test_pop3.py` logged in to the POP3 mailbox, both successfully. `mail_import.py` and `mail_filter.example.py` are written and pass a check against a local fake POP3 server and a fake Gmail endpoint. On 2026-09-16 a check of the same kind covered the rejection path, with the fake endpoint returning 400, 413, and 503. On 2026-09-16 `mail_import.py` also imported mail successfully from a test POP3 mailbox, which is what the maintainer's `.env` points at for now. It has not run against the real mailbox yet. `mail_filter.py` exists on the maintainer's host as of 2026-09-19 and discarded a message during the runs that day. Whether it is the rule the real mailbox will need is not recorded here. README now says the implementation is written and has handled real mail. `docs/USAGE.md` and its translation describe running the tool, the state file, and dealing with a rejected message. `tools/show_info_from_uidl.py` is written and passes a check against a local fake POP3 server with synthetic mail. On 2026-09-16 it also showed a plain message and a message with an attachment in the test POP3 mailbox as expected. It has not been tried on a real rejected message yet.

On 2026-09-18 the per-run limit was added as `MAX_MESSAGES_PER_RUN`, because the mailbox the tool is meant for receives far more mail per day than one run should take in one session. It was checked with a fake POP3 session and a fake import over eight cases, covering a listing above, at, and below the limit, a limit of 0, entries the state file records as imported or rejected inside the window, a discarded message, a rejection with a remainder left over, and a state line for a message past the limit surviving the startup pruning. README, `docs/USAGE.md`, `.env.example`, and the translations were updated in the same change, and the README requirement now reads as keeping the mailbox empty rather than emptying it on every run.

On 2026-09-19 `tools/run_cron.sh` was added, with `docs/USAGE.md` and its translation updated in the same change. On 2026-09-19 the limit was exercised end to end against the test POP3 mailbox, with `MAX_MESSAGES_PER_RUN` set to 1 and three messages waiting. Four runs in a row reported `deferred` as 2, 1, 0, and 0, importing two messages and discarding one, all with exit status 0. The state file was empty afterwards, which is the startup pruning dropping each `imported` line once its message had left the server. The real mailbox has still not been touched, and the limit has not been exercised at its default of 200. The maintainer's `.env` still carries the test value of 1, so it has to go back to 200 before the tool is scheduled.
