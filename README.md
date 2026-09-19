# pop3-to-gmail-import

[日本語の説明はこちら](docs/README.ja.md)

Imports mail from a POP3 mailbox into Gmail through the Gmail API, and discards selected messages before they ever reach Gmail.

This repository exists mainly to record *why* it is built the way it is. The code is small and fitted to one person's situation. If you arrived here looking for a way to keep receiving POP3 mail in Gmail, the reasoning below is probably more useful to you than the code.

## You probably do not need this

Gmail no longer lets new users fetch mail from other accounts over POP3, and existing users lose the feature in January 2027. For most people there are better options than this project.

- **If you can configure forwarding on the source mail server, do that.** Forwarding at the first hop, meaning the server that accepted the message from the sender, is the best-behaved option. Gmail can then still evaluate the sender's SPF record and the original connection.
- **If you simply want every message imported, use an existing, more complete tool.**
  - [gmail-importer3](https://github.com/kyokuheki/gmail-importer3) imports from POP3 or IMAP through the Gmail API.
  - [Fetch2Gmail](https://pypi.org/project/fetch2gmail/) imports from IMAP with idempotent state tracking.
  - [Turbogmailify](https://github.com/YoRyan/turbogmailify) imports from IMAP and can use IDLE for near real-time delivery.
  - InboxBridge is a self-hosted importer with a web UI.

This project only makes sense if you cannot forward at the source, you need to drop some messages before they are stored anywhere, *and* reading the mail is all you have to do with it. The last point is important enough to spell out.

## It only solves receiving

This tool moves mail in one direction. It takes messages out of the POP3 mailbox and puts them into Gmail. It does nothing at all about sending.

Replying to an imported message in Gmail sends the reply from the Gmail address, not from the address the sender wrote to. The other party sees a different address, replies to that one from then on, and the conversation moves off the original address. Gmail's "Send mail as" can register another address, but sending through it still needs an SMTP server on the other side, with a host name, a user name, and a password. A POP3-only mail service does not necessarily offer one that Gmail can use, and an employer may not permit it even where it exists. Nothing in this project fills that gap.

The author only has to read this mail and answers elsewhere, so this costs nothing here. The design follows from that, and it is a convenience of the author's own situation rather than a general solution.

If you have to reply from the address, consolidating it into Gmail may well be an anti-pattern for you. Look at another solution instead, such as a mail client that keeps the account as its own account and sends through the provider's server. Decide that before you point this tool at a mailbox, because once the mailbox is being emptied into Gmail, the sending half of the problem is still waiting.

## Why this exists

The author's employer runs a POP3-only mail server. Forwarding cannot be set up from the user side, and asking the administrators is not expected to lead anywhere soon. The mailbox is small and fills up quickly, so it has to be emptied regularly.

The address is also subscribed to a sales department mailing list. Mail sent to that list often carries attachments the author should not keep, such as spreadsheets containing customer data. The author has no use for them and can ask the department directly when needed. A Gmail filter could delete these messages, but deleted mail stays in Gmail's trash for 30 days. The goal is to never store them at all.

The requirements are therefore these.

- Keep the POP3 mailbox empty, by deleting from it whatever has been dealt with.
- Read mail in Gmail on both desktop and phone, and rely on Gmail's spam filtering.
- Drop messages that have the list address in To or Cc *and* carry an attachment, before they reach Gmail.

## Design decisions

### Import, not insert or IMAP APPEND

There are several ways to put a message into a Gmail mailbox. The Gmail API method `users.messages.import` runs the message through standard delivery scanning and classification, similar to receiving it over SMTP. `users.messages.insert` and IMAP `APPEND` place the message directly and skip spam classification. Since spam filtering is left entirely to Gmail, this project uses `import`.

### Not SMTP forwarding, even with SRS

It is tempting to forward over SMTP with SRS and ARC, the way a "proper" forwarder would. It does not help here.

Only the server that accepted the message from the original sender can evaluate the sender's SPF record and connecting IP. This tool sits behind that server and fetches over POP3, so it never has that information. With SRS, Gmail would check SPF against the relay's own domain, which says nothing about the original sender. ARC does not help either, because the relay has no trustworthy authentication results to seal.

SMTP forwarding would also create new problems.

- A spam-heavy mailbox would be relayed from the relay's IP and domain, damaging their reputation with Gmail.
- Residential IPs are often rejected, and outbound port 25 is commonly blocked.
- Amazon SES and similar services only send from verified addresses, so they cannot relay mail from arbitrary senders.

### What Gmail loses and what it keeps

With `import`, Gmail cannot evaluate SPF or the original connecting IP. DKIM signatures are part of the message itself, so they stay verifiable as long as the bytes are not modified. The tool therefore passes the message exactly as fetched and never parses and re-serializes it before upload. It uses the media upload endpoint so the raw message is sent as is, rather than base64-encoded inside JSON.

Gmail's own POP3 fetch also retrieved mail after the first hop, so it presumably worked under similar conditions. How Gmail weighs authentication results on import is not documented, though. Spam filtering quality should be checked against real spam before relying on it.

### Delete only after a confirmed result

A message is deleted from the POP3 server only after Gmail confirms the import, or after the tool deliberately discards it. On any error the message stays on the server and is retried on the next run. The failure mode is mail piling up on the server, not mail being lost.

Because the source mailbox is small, a pile-up still becomes a problem quickly. The tool exits with a non-zero status on failure and is meant to be paired with some form of failure notification.

### A limit on each run

A run handles at most `MAX_MESSAGES_PER_RUN` messages, 200 by default, and leaves the rest on the server for the next run. A mailbox with a backlog, or one that receives a lot of mail, would otherwise keep a single run going for a long time. That is worth avoiding, because a POP3 server locks the mailbox for the length of a session, and because an error late in a long run leaves everything after it unhandled anyway.

Messages are handled in the order the server lists them, which is the order they arrived, so the oldest are always the ones that go first. The limit means the mailbox is emptied over several runs rather than one, and it only keeps up if the schedule is frequent enough for the amount of mail that arrives. The default of 200 matches what Gmail's own POP3 fetch retrieved at a time.

### Filtering before import

A message is discarded when the configured list address appears in To or Cc and at least one MIME part has a filename. Inline images in signatures count as attachments under this rule. The rule is intentionally crude. False positives are acceptable because anything important can be requested again from the sender.

### Cost

Standard use of the Gmail API is free. One `messages.import` call costs 25 quota units. The per-project daily billing threshold is 80,000,000 units, and the per-user limit is 6,000 units per minute. A single mailbox is nowhere near either.

## Status

The design above is settled, and the implementation is written. It has fetched real mail over POP3, applied the rule, and imported the result into Gmail. It has not been in use for long, so read the code before pointing it at a mailbox that matters.

## Setup and usage

Account and API setup that has to be done by hand is described in [docs/SETUP.md](docs/SETUP.md). Running the tool, and dealing with a message it could not import, is described in [docs/USAGE.md](docs/USAGE.md).
