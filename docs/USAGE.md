# Usage

[日本語の説明はこちら](USAGE.ja.md)

This document covers running the tool once the setup in [SETUP.md](SETUP.md) is done, what its output and its state file mean, and what to do with a message it could not import.

## Before the first run

### Finish the setup

Complete every step of [SETUP.md](SETUP.md), including the tests in steps 10 and 11, so that `.env` holds working POP3 and Gmail settings.

A relative path in `.env`, for either `GOOGLE_CLIENT_SECRET_FILE` or `STATE_FILE`, is resolved against the repository root. That holds whatever directory the tool is started from, so a scheduler can start it from anywhere.

### Write the filter rule

The rule that decides which messages are discarded lives in `mail_filter.py`, which is not part of the repository. Create it by copying the example in the repository root.

```
cp mail_filter.example.py mail_filter.py
```

Without this file the tool stops with `error: mail_filter.py not found`. The copy discards nothing, so every message is imported until you write a rule. The docstring of `should_discard()` in the file shows how to read the subject, the addresses, and the attachments of a message, and a commented example rule follows it.

`mail_filter.py` is listed in `.gitignore`, since a real rule usually names real addresses. When the tool moves to another host, copy `mail_filter.py` by hand along with `.env`.

A message the rule discards is deleted from the POP3 server without being stored anywhere, and it cannot be recovered. Try a new rule on a test mailbox, with messages you send yourself, before using it on a mailbox that matters.

If the rule raises an exception, the message is neither imported nor deleted. See [Errors](#errors).

### Know what the first run does

The first run handles what is on the POP3 server now, up to `MAX_MESSAGES_PER_RUN` messages, 200 by default. Each one is either imported into Gmail or discarded by the rule, and then deleted from the server. A mailbox holding more than that is emptied over the runs that follow. If you want to keep a copy of what is on the server now, download it with a regular mail client first.

## Running the tool

Run the following from the repository root.

```
python3 mail_import.py
```

A run goes through these steps.

1. Refresh the Gmail access token.
2. Log in to the POP3 server and list the messages by UIDL.
3. For each message, up to `MAX_MESSAGES_PER_RUN` of them, retrieve it and evaluate the rule. The message is then either deleted, or imported into Gmail and deleted. Messages already in the state file are handled as described in [The state file](#the-state-file).
4. End the session with `QUIT`. This is when the POP3 server actually deletes the messages.

When the run gets through the POP3 session, it ends by printing one line of counts to standard output.

```
imported=3 discarded=1 rejected=0 skipped=0 deferred=0
```

- `imported` is the number of messages imported into Gmail with the `INBOX` and `UNREAD` labels and deleted from the server.
- `discarded` is the number of messages the rule discarded. They were deleted without being imported.
- `rejected` is the number of messages Gmail refused in this run. They stay on the server.
- `skipped` is the number of messages Gmail refused in an earlier run. They stay on the server and are not sent again.
- `deferred` is the number of messages the run did not reach, because it had taken `MAX_MESSAGES_PER_RUN` messages already. They stay on the server, and the next run takes them first.

The tool exits with status 0 when nothing in the run failed, and with a non-zero status otherwise. Messages skipped as rejected in an earlier run do not count as a failure. Errors go to standard error.

Output names a message only by its UIDL, never by its subject or sender, so it can be kept in logs.

### How much one run handles

`MAX_MESSAGES_PER_RUN` in `.env` sets how many messages a run takes from the listing, 200 by default. Anything past it is left on the server and counted as `deferred`. Reaching the limit is not a failure, so the run still exits with status 0.

The limit counts every entry in the listing, including a message that is only skipped because an earlier run recorded it as rejected. Messages are taken in the order the server lists them, which is the order they arrived, so the oldest always go first.

A mailbox is therefore emptied over several runs rather than one. If runs keep ending with a `deferred` count, mail is arriving faster than the schedule and the limit together can carry. Run the tool more often, or raise the value.

### Errors

Every error line starts with `error:`. A line that names a UIDL concerns that one message.

- `error: <UIDL> rejected by Gmail with HTTP 400`, or `HTTP 413`

  Gmail refused the message itself. 413 means it is too large. The message stays on the server and is recorded as rejected, so later runs skip it. Only this run exits non-zero, so the error is reported once. See [When Gmail rejects a message](#when-gmail-rejects-a-message).

- `error: <UIDL> filter raised <exception> at mail_filter.py line <n>`

  The rule raised an exception on this message. The message stays on the server and is not recorded, and the other messages are still handled. Every run fails the same way until the rule is fixed. `tools/show_info_from_uidl.py`, described in [When Gmail rejects a message](#when-gmail-rejects-a-message), shows which message it is.

- `error: <UIDL> import failed, <reason>`

  Gmail could not be reached, or it refused the request for a reason that concerns the account or the service, such as HTTP 401, 403, 429, or 5xx. The run stops there. Messages handled so far are deleted, and the rest wait for the next run. If it keeps failing with 401 or 403, see [When the refresh token stops working](SETUP.md#when-the-refresh-token-stops-working).

- `error: token refresh returned <status> <response>`, or `error: token refresh failed, <reason>`

  The access token could not be refreshed, and nothing is fetched. If it persists, see [When the refresh token stops working](SETUP.md#when-the-refresh-token-stops-working).

- Any other `error:` line

  The POP3 connection or its settings failed, for example at login. Deletions only take effect at `QUIT`, so no message is deleted in this run. Messages this run had already imported are recorded in the state file, and the next run deletes them without importing them again.

### Running on a schedule

The tool runs once and exits. To keep the mailbox empty, start it from a scheduler such as cron, at whatever interval suits you. It finds `.env`, `mail_filter.py`, and the state file next to `mail_import.py`, so the scheduler can start it by its full path from any directory.

`tools/run_cron.sh` is a wrapper written for exactly that. It writes the date and time around the run, so a log shows when each run started and ended, and it takes a lock on `.cron.lock` in the repository root, so that two runs never overlap. Add a line like the following to your crontab with `crontab -e`, with the interval you want.

```
*/30 * * * * /path/to/pop3-to-gmail-import/tools/run_cron.sh
```

Its output looks like this.

```
2026-09-19T01:20:00+0900 start
imported=3 discarded=1 rejected=0 skipped=0 deferred=0
2026-09-19T01:20:12+0900 end status=0 seconds=12
```

The wrapper exits with the importer's own status, so a failure still reaches whatever watches the job. cron mails what the job writes to the owner of the crontab. To keep a log file instead, redirect in the crontab line, as the comment at the top of the script shows.

Pair it with some form of failure notification. A non-zero exit status is the only sign that something needs attention. A `deferred` count is not one of those signs, since the run ends with status 0, so watch the counts as well if the mailbox is a busy one.

A POP3 mailbox can be used by only one session at a time, so runs must not overlap. The lock in `tools/run_cron.sh` is what keeps them apart. A run that finds the lock held prints `not started, another run holds ...` and exits 0, since one overlap is not a failure in itself. If that line keeps appearing, runs are taking longer than the interval between them, and the schedule or the limit needs looking at.

A mail client checking the same mailbox is outside that lock. A run that meets one fails at login and exits non-zero, and the next run tries again.

## The state file

The tool records some messages in a state file, so that a later run knows what already happened to them. Its path is `STATE_FILE` in `.env`, `state.txt` by default, and a relative path is resolved against the repository root. The file is created on the first run and is listed in `.gitignore`.

Each line holds a status and a UIDL, the identifier the POP3 server gives each message.

```
imported 000001a2b3c4d5e6
rejected 000001a2b3c4d5e8
```

- `imported` means the message was imported into Gmail. The line is written before the message is deleted from the server. If the session then fails before the deletion takes effect, the next run finds the message still on the server and deletes it without importing it a second time.
- `rejected` means Gmail refused the message. It stays on the server, and later runs skip it and count it as `skipped`.

Messages discarded by the rule are not recorded, since evaluating the rule again gives the same result.

At the start of every run, lines for messages that are no longer on the server are removed. This looks at the whole mailbox, not only at the messages the run goes on to handle. Once you delete a rejected message from the server, the next run removes its line, and the file never grows beyond what is on the server.

The file holds UIDLs only, never anything taken from the messages.

Do not edit the file while the tool is running. The only reason to edit it by hand is to retry a rejected message, by removing its `rejected` line. Do not remove `imported` lines, since that can import a message twice.

## When Gmail rejects a message

A rejected message stays on the POP3 server, taking up space there, until you deal with it. The tool's output names it only by its UIDL, so follow these steps to find out what it is.

### 1. Find the UIDL

Take the UIDL from the error line, such as `error: 000001a2b3c4d5e8 rejected by Gmail with HTTP 400`, or from a `rejected` line in the state file.

### 2. Look the message up

Run the following from the repository root, with the UIDL as the argument.

```
python3 tools/show_info_from_uidl.py 000001a2b3c4d5e8
```

It reads the POP3 settings from `.env`, retrieves the message, and prints what you need to recognize it.

```
Subject:     Quarterly report
From:        Example Sender <sender@example.net>
To:          user@example.com
Cc:
Date:        Tue, 15 Sep 2026 10:11:00 +0000
Received:    Tue, 15 Sep 2026 10:11:12 +0000
Message-ID:  <20260915101100.12345@mail.example.net>
Attachments: 1
Size:        48,213 bytes
```

- `Date` is set by the sender and can be wrong, especially on spam. `Received` is the date on the topmost `Received` header, which usually shows when the POP3 server accepted the message.
- `Attachments` counts the MIME parts that have a filename, the same test as the example rule in `mail_filter.example.py`. Inline images, such as those in signatures, count too.
- `Size` is the size of the whole message as the server holds it, which is also what the tool uploads to Gmail. Attachments are encoded inside the message, which makes them about a third larger than the files themselves.

A header that cannot be decoded is printed as it appears in the message, and control characters are shown escaped, such as `\x1b`.

The tool never deletes the message and writes nothing to disk. Its output does show the subject and the addresses, so do not send it to a log. Like the importer, it cannot log in while another session holds the mailbox, so run it when the importer is not running.

If the message is no longer on the server, it prints `error: <UIDL> is not on the server` and exits with a non-zero status.

### 3. Open the message in a mail client

The output above is meant for finding the message, not for reading it. To see the body, the attachments, or all of the headers, open the mailbox in a regular POP3 client such as Thunderbird, or in the server's webmail if it has one, and find the message by its subject, sender, and date.

A POP3 client works on the same mailbox as the tool, so check its account settings before it connects.

- Make it leave messages on the server, and not remove them after a set number of days. Otherwise it deletes the messages it downloads, and those never reach Gmail.
- Turn off its automatic checks for new mail, so it does not hold the mailbox while the tool runs.

The client also downloads messages the tool has not handled yet. As long as they are left on the server, the next run imports them as usual.

### 4. Resolve the message

Once you know what the message is, save anything you need from it, and delete it from the server with the mail client or the webmail. The next run removes its line from the state file.

To have the tool try the import once more instead, remove its `rejected` line from the state file. The next run sends it to Gmail again.
