# Privacy Policy

This policy covers pop3-to-gmail-import, a self-hosted tool that moves mail from a POP3 mailbox into the Gmail account of the person running it.

## Who operates it

The tool is not a hosted service. Each person who uses it runs it on a machine they control, with their own Google Cloud project and OAuth client. The author of this repository does not operate any server for it and does not receive any data from people who use it.

## What data it accesses

- **Mail in the configured POP3 mailbox.** The tool downloads each message, then either imports it into Gmail or discards it according to the configured filter rule. After that, the message is deleted from the POP3 server.
- **The Gmail account that granted access.** The tool requests only the `https://www.googleapis.com/auth/gmail.insert` scope. It uses this scope to add messages to the mailbox with `users.messages.import`. It cannot read, modify, or delete existing mail in the account.

## What data it stores

The tool keeps messages only in memory, and only for as long as it takes to import or discard them. Discarded messages are not written anywhere.

The POP3 credentials, the OAuth client secret, and the OAuth refresh token are stored on the machine where the tool runs, under the control of the person running it.

## Who data is shared with

Messages are sent only to the Gmail API, and only to the Gmail account that granted access. The tool sends no data to the author or to any other third party, and it contains no analytics or telemetry.

## Google API Services User Data Policy

Use of information received from Google APIs adheres to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.

## Revoking access

Access can be revoked at any time from [Google Account permissions](https://myaccount.google.com/permissions). Revoking access stops the tool from importing further messages.

## Contact

Questions about this policy can be raised as an issue in this repository.
