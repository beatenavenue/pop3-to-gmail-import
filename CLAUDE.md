# CLAUDE.md

Guidance for Claude and other AI assistants working in this repository.

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

The tool is started by cron. The schedule can then differ by day and hour, which matters because this is work mail and weekday daytime volume is far higher than the weekend. Nothing in the tool may assume a fixed interval between runs.

Obtaining the refresh token is a separate one-off program. Keep it out of the import path, since the import path runs unattended and never needs a browser.

The following are still open. Ask the user instead of choosing one.

- Which host the tool runs on. Do not write deployment files before this is settled
- What to do with a message Gmail rejects permanently, since retrying it forever keeps it on the server
- Whether to keep a record of imported UIDLs, so an interrupted session does not import the same message twice. This is what getmail6 used its oldmail file for. It stores message identifiers, not message content

## Scope

Keep the project small. The goal is a minimal, readable reference, not a general-purpose importer. Established alternatives are listed in README.md. Ask the user before adding features, dependencies, or configuration beyond what the current task needs.

The two halves of this project are not held to the same standard. Fetching mail and putting it into Gmail is a commodity that many tools already implement, so that path stays as small as it can be, and anything the standard library already does is not reimplemented here. The rule that decides which messages are destroyed is specific to this project, and it is allowed to grow as the maintainer needs.
