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

## Scope

Keep the project small. The goal is a minimal, readable reference, not a general-purpose importer. Established alternatives are listed in README.md. Ask the user before adding features, dependencies, or configuration beyond what the current task needs.
