# Connect an X account to your app

This script lets your app post (and read) on behalf of an X account that is
**not** the account that created the app.

## The idea, in one paragraph

Think of "Sign in with Google" buttons. A website asks for permission, you
click Allow, and the website gets a key that works for your account only.
Your X app works the same way. The developer portal gives you a key for the
account that owns the app, and that is all it will ever give you. Any other
account has to click Allow itself. This script is what shows them the Allow
screen and catches the key that comes back.

So: **one app, many keys, one key per account.**

## What you need before starting

- Python 3.7 or newer. Check with `python --version`.
- An X app with user authentication turned on. In the developer portal, open
  your app, go to **User authentication settings**, and set:
  - App permissions: **Read and write**
  - Type of App: **Web App, Automated App or Bot**
  - Callback URI: `http://localhost:3000/callback`
  - Website URL: anything valid, e.g. `https://example.com`
- The **Client ID** and **Client Secret** from that app, found under
  **Keys and tokens**. These are not the same as the API Key or Access Token
  shown higher up on that page. You want the OAuth 2.0 pair.

## Setup (once)

Copy the example settings file and fill in your two values:

```
copy .env.example .env        # Windows
cp .env.example .env          # Mac / Linux
```

Open `.env` in any text editor and paste your Client ID and Client Secret
after the `=` signs. No quotes needed. Save it.

`.env` is ignored by git, so your secret will not end up in the repo.

## Connecting an account

Run the script with a name for the account you are connecting:

```
python connect_x_account.py gap_pre_prod_1
```

A browser window opens showing X's permission screen.

**Look at the handle on that screen before clicking anything.** It shows
whichever account your browser is currently signed in as, which is very
often the wrong one. If it does not match the account you are trying to
connect:

1. Leave that tab alone -- do not press Cancel.
2. Copy the long URL the script printed in your terminal.
3. Open a private/incognito window (Ctrl+Shift+N, or Cmd+Shift+N on Mac).
4. Sign in to x.com as the account you actually want.
5. Paste the URL there.

When the handle looks right, click **Authorize app**. The browser will show
"Done. You can close this tab." and your terminal will print which account
was authorized.

The result is saved to `tokens/gap_pre_prod_1.json`. That folder is also
gitignored.

Repeat the command with a different name for each account you want to
connect. They do not interfere with each other.

## What you actually got

Look inside the saved file and you will see a `refresh_token`. That is the
long-lived one, and it is the only thing worth keeping.

You did **not** get a permanent password. The token that actually makes API
calls (the access token) lasts two hours and is deliberately not saved. Your
application code trades the refresh token for a fresh access token whenever
it needs one:

```python
import requests

r = requests.post(
    "https://api.x.com/2/oauth2/token",
    auth=(CLIENT_ID, CLIENT_SECRET),
    data={"grant_type": "refresh_token", "refresh_token": stored_refresh_token},
)
new = r.json()
access_token = new["access_token"]

# CRITICAL: save this. The old refresh token is now dead.
save_somewhere(new["refresh_token"])
```

**Read that last part twice.** Every refresh gives you a new refresh token
and kills the old one. If your code forgets to save the new one, the next
run fails and you have to rerun this script by hand. This is the single most
common way these setups break.

Then post with it:

```python
requests.post(
    "https://api.x.com/2/tweets",
    headers={"Authorization": f"Bearer {access_token}"},
    json={"text": "hello from the api"},
)
```

## Optional settings

You can add these to `.env` if you need them:

| Variable | Default | What it does |
|---|---|---|
| `X_REDIRECT_URI` | `http://localhost:3000/callback` | Must match the portal exactly, trailing slash included |
| `X_SCOPES` | `tweet.read tweet.write users.read offline.access` | What the app is allowed to do |

To let an account follow or unfollow others, add `follows.write` to
`X_SCOPES` and run the script again for that account. Permissions are fixed
at the moment you click Authorize, so changing scopes always means
reconnecting.

Keep `offline.access` in the list. Without it you get no refresh token, and
everything stops working after two hours.

## When something goes wrong

**"Missing X_CLIENT_ID"** -- there is no `.env` file, or the value is blank.

**Browser says something about a callback or redirect URI** -- the value in
`.env` does not exactly match the one saved in the developer portal. Compare
them character by character; a trailing slash is enough to break it.

**"Address already in use"** -- something else is on port 3000. Stop it, or
change the port in both the portal and `.env`.

**Script prints a warning that the handle does not match the label** -- you
authorized while signed in as the wrong account. Rerun and use a private
window.

**A 401 or 403 when posting** -- either the access token has expired
(refresh it) or your app is missing write permission. Check that App
permissions in the portal say Read and write. If you change that setting,
you must reconnect the account for it to take effect.

**403 on follows or other endpoints** -- some endpoints are not available on
the Free access tier, even with the right scope.

## Notes on safety

Do not commit `.env` or the `tokens/` folder. The `.gitignore` handles this
already, but check with `git status` before your first push.

If a secret does leak, regenerate it in the developer portal. To disconnect
an account, sign in as that account and go to Settings, Security and account
access, Apps and sessions, Connected apps, then revoke.
