# Setup

[日本語の説明はこちら](SETUP.ja.md)

This document covers the one-time setup that has to be done by hand before the tool can run, from creating the Google Cloud project to testing the OAuth refresh token and the POP3 connection. Running the tool itself is covered in [USAGE.md](USAGE.md).

Google Cloud console labels change from time to time. If a menu name below does not match what you see, look for the closest equivalent.

## Before you start

Decide which Gmail account will receive the imported mail. This is the account you will authorize later, and it does not have to be the account that owns the Google Cloud project.

Consider testing with a separate, throwaway Gmail account first. Mail imported during testing cannot be un-imported cleanly, and a separate account keeps your real inbox untouched.

## 1. Create a Google Cloud project

1. Open the [Google Cloud console](https://console.cloud.google.com/) and sign in with any Google account.
2. Open the project selector at the top of the page and choose **New project**.
3. Give it any name and create it.

A billing account is not required. Standard use of the Gmail API is free.

## 2. Enable the Gmail API

1. With the new project selected, go to **APIs & Services** > **Library**.
2. Search for **Gmail API**, open it, and click **Enable**.

## 3. Configure the OAuth consent screen

OAuth settings live under **Google Auth Platform** (older console versions call this the **OAuth consent screen**).

1. Go to **Google Auth Platform** and click **Get started** if prompted.
2. Under **Branding**, fill in the following and save.
   - **App name** and **User support email**. Only you will see these.
   - **Application home page**. The URL of this repository (or your fork) works, for example `https://github.com/<user>/pop3-to-gmail-import`.
   - **Application privacy policy link**. Point it to [PRIVACY.md](PRIVACY.md) in the same repository, for example `https://github.com/<user>/pop3-to-gmail-import/blob/main/docs/PRIVACY.md`.
   - **Authorized domains**. Add the domain used by the two links above, which is `github.com` in this example.
   - **Developer contact information**. Your email address.

   The home page and privacy policy are optional while the app is in **Testing**, but the app cannot be published to production without them (see step 5). They are not reviewed, since this app never goes through verification, but they should point to pages that actually exist.
3. Under **Audience**, choose **External** as the user type. **Internal** is only available to Google Workspace organizations.
4. Under **Data Access**, click **Add or remove scopes** and add the following scope manually.

   ```
   https://www.googleapis.com/auth/gmail.insert
   ```

   This scope allows adding messages to the mailbox, which covers `users.messages.import`. It does not allow reading or deleting existing mail.

## 4. Create an OAuth client

1. Under **Clients**, click **Create client**.
2. Choose **Desktop app** as the application type and create it.
3. Download the client JSON file.

This file contains the client secret. Keep it out of the repository and out of any shared location.

## 5. Publish the app to production

Under **Audience**, click **Publish app** and confirm.

If the button is disabled, the branding configuration is incomplete. Hovering over the button shows what is required. In particular, the home page and privacy policy links from step 3 are mandatory for production even though the Branding page does not mark them as required.

Do this *before* authorizing. While the publishing status is **Testing**, refresh tokens for external users expire after 7 days, and the tool would stop working every week.

Publishing does not make the app public or searchable. Because `gmail.insert` is a sensitive or restricted scope and the app is not verified, Google will show an "unverified app" warning when you authorize. Google allows unverified apps for personal use by fewer than 100 users, so no verification or security assessment is needed.

When you authorize later, the warning is passed by choosing **Advanced** and then **Go to (app name)**.

## 6. Prepare the Gmail account

If this Gmail account currently fetches the same POP3 mailbox through **Settings** > **See all settings** > **Accounts and Import** > **Check mail from other accounts**, remove that entry when you switch over. Two fetchers on one POP3 mailbox will race for the same messages.

Removing it is a one-way step. Gmail no longer accepts new POP3 fetch entries, so it cannot be added back.

## 7. Gather the POP3 details

Collect the following for the source mailbox.

- Host name
- Port, usually 995 for POP3 over TLS or 110 for plain POP3
- Whether TLS is required or supported
- User name and password

If the server offers webmail, check whether messages deleted over POP3 are actually removed or only moved to a trash folder. If they are kept in a trash folder, the mailbox will still fill up.

## 8. Obtain the refresh token

Do this on a machine with a web browser, after step 5. The tool itself can run on a different, headless host, because a refresh token is tied to the OAuth client and the Gmail account, not to the machine it was obtained on.

1. Run the following from the repository root, passing the client JSON downloaded in step 4.

   ```
   python3 tools/get_google_refresh_token.py /path/to/client_secret.json
   ```

2. A browser opens Google's consent page. If it does not open, copy the URL printed in the terminal into a browser on the same machine.
3. Sign in with the Gmail account that will receive the mail, pass the unverified app warning as described in step 5, and allow access.
4. When the browser shows "Response received. Return to the terminal.", go back to the terminal. The refresh token is printed on the last line.

The program waits for Google's redirect on `127.0.0.1`, so the browser has to run on the same machine as the program. Running it on a remote host over SSH does not work.

Each run issues a new refresh token. Only the 100 most recent tokens for the same client and account stay valid, so avoid running it more often than needed.

## 9. Configure the host that runs the tool

The host needs the client JSON as well as the refresh token, because refreshing an access token also sends the client ID and secret.

1. In the repository root on that host, copy `.env.example` to `.env`. Write every value without quotes.
2. Set the POP3 details from step 7 as `POP3_HOST`, `POP3_PORT`, `POP3_TLS`, `POP3_USER`, and `POP3_PASSWORD`. Set `POP3_TLS` to `true` when the connection uses TLS from the start, usually on port 995, or to `false` for plain POP3 on port 110, which the tool upgrades with STLS. The tool never connects without TLS.
3. Copy the client JSON to the host, outside the repository, and set its path as `GOOGLE_CLIENT_SECRET_FILE`.
4. Set the refresh token from step 8 as `GOOGLE_REFRESH_TOKEN`.
5. Make both files readable only by your user.

   ```
   chmod 600 .env /path/to/client_secret.json
   ```

Treat the refresh token like a password. Move it with `scp` or by typing it into a terminal on the host, not through chat or a synced clipboard.

## 10. Test the refresh token

Run the following from the repository root on the host.

```
python3 tools/test_insert.py
```

This reads `.env`, refreshes an access token, and adds one synthetic message to the Gmail account with the subject `pop3import test` and the body `pop3import API test`. It uses the same API method, upload endpoint, and labels as the tool. On success it prints the new message ID and the labels Gmail applied. On failure it prints the error returned by Google and exits with a non-zero status.

**The test message will almost certainly go to the Spam folder, not the inbox.** It comes from a placeholder address at `example.com` and has no DKIM signature, so Gmail treats it as spam. This is expected and does not mean the test failed. Look for it in Spam and delete it when you are done.

Each run adds one more message.

## 11. Test the POP3 connection

Run the following from the repository root on the host.

```
python3 tools/test_pop3.py
```

This reads `.env`, connects to the POP3 server with TLS the same way the tool does, logs in, and prints the number of messages in the mailbox, for example `connected messages=12`. It never retrieves or deletes a message, so the mailbox is left as it was. On failure it prints the error and exits with a non-zero status.

If the server offers webmail, the count should match the number of messages in its inbox.

POP3 servers usually lock the mailbox while a session is open. If Gmail still fetches this mailbox (see step 6) or a mail client is checking it at the same moment, the login can fail. Wait a little and run it again.

With `POP3_TLS=false`, the server has to list `STLS` in its reply to the `CAPA` command. A server that offers neither POP3 over TLS nor STLS cannot be used.

## When the refresh token stops working

A refresh token that worked before can become invalid in these cases.

- The app was still in **Testing** status (the 7-day expiry described above)
- You revoked access at [Google Account permissions](https://myaccount.google.com/permissions)
- You changed the Google account password, since tokens with Gmail scopes are revoked on password change
- The token went unused for six months
- More than 100 refresh tokens were issued for the same client and account, which invalidates the oldest ones

In any of these cases, obtain a new refresh token as in step 8 and replace `GOOGLE_REFRESH_TOKEN` in `.env`.
