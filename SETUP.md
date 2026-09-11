# Setup

This document covers the steps that have to be done by hand in a browser, before any code is run. Running the tool and obtaining the OAuth refresh token are covered separately.

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
2. Under **Branding**, enter an app name and a support email. Only you will see these.
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

## When the refresh token stops working

A refresh token that worked before can become invalid in these cases.

- The app was still in **Testing** status (the 7-day expiry described above)
- You revoked access at [Google Account permissions](https://myaccount.google.com/permissions)
- You changed the Google account password, since tokens with Gmail scopes are revoked on password change
- The token went unused for six months
- More than 100 refresh tokens were issued for the same client and account, which invalidates the oldest ones

In any of these cases, authorize again to obtain a new refresh token.
