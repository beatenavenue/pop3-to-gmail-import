# Privacy Policy

[日本語の説明はこちら](PRIVACY.ja.md)

pop3-to-gmail-import is not a hosted service. It is source code that each person runs on their own machine, with their own Google Cloud project and their own OAuth client. Nobody operates a shared instance of it.

That makes an ordinary privacy policy an awkward fit. This document exists because the Google Cloud console requires a privacy policy URL before an OAuth app can be published, and because anyone who publishes their own copy needs to know what they are taking responsibility for.

## Scope of this document

This policy describes the unmodified source code in this repository, as published by its author.

It does not describe any particular deployment. Whoever runs a copy of this code decides what it does, where it runs, and what happens to the mail it handles. A modified copy can behave differently in every respect described below.

## If you run your own copy

You are the operator of your deployment, and the author of this repository is not. The author has no access to it, no knowledge of it, and no responsibility for it.

Do not submit this document as the privacy policy for your own OAuth app. Write your own, describing what your deployment actually does. Reusing this one would misdescribe your deployment and would point your users at someone who cannot answer for it.

## What the code does with Google user data

- It requests a single OAuth scope, `https://www.googleapis.com/auth/gmail.insert`. This scope permits adding messages to a mailbox. It does not permit reading, modifying, or deleting messages already in the account.
- It uses that scope for one purpose, calling `users.messages.import` to place mail fetched from a POP3 mailbox into the Gmail account that granted access.
- It sends no data anywhere else. There are no analytics, no telemetry, and no reporting back to the author or to any third party.

Use of information received from Google APIs adheres to the [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy), including the Limited Use requirements.

## Credentials

The POP3 credentials, the OAuth client secret, and the OAuth refresh token are held by the operator on the machine where the code runs. The code does not transmit them anywhere other than to the POP3 server and to Google.

Access can be revoked at any time from [Google Account permissions](https://myaccount.google.com/permissions).

## Contact

Questions about this document can be raised as an issue in this repository. Questions about a particular deployment should go to whoever runs it.
