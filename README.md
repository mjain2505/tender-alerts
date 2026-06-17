# Tender Alert System (Musical Fountain / Misting Systems)

This automatically checks Indian government tender portals every 3 hours for
tenders matching your dad's keywords, and instantly emails + Telegrams you
when a new one shows up.

It costs ₹0/month to run.

---

## What it checks automatically right now

These run the exact same government software (NIC "GePNIC"), confirmed working:

- Central Government — CPPP (covers all central ministries, PSUs, IITs, AIIMS, etc.)
- Uttar Pradesh
- Maharashtra
- Rajasthan
- Madhya Pradesh
- West Bengal
- Tamil Nadu

These are included too (same software, very likely correct, not personally re-verified — if one comes back empty in the logs, send me the portal name and I'll fix the URL):

Punjab, Haryana, Bihar, Odisha, Jharkhand, Himachal Pradesh, Uttarakhand,
Chhattisgarh, Assam, Kerala, Jammu & Kashmir.

## States you'll need to check manually for now

These run *different* software than the rest (so they need separate custom
scraping logic I haven't built yet) — bookmark these and check every few days,
or tell me to build automation for a specific one next:

- **Gujarat** — https://nprocure.com
- **Karnataka** — https://eproc.karnataka.gov.in
- **Telangana** — https://tender.telangana.gov.in
- **Andhra Pradesh** — https://tender.apeprocurement.gov.in
- **Delhi (NCT)** — https://govtprocurement.delhi.gov.in
- **Goa** — https://goaenivida.gov.in
- Smaller states/UTs not listed above (Manipur, Meghalaya, Mizoram, Nagaland,
  Sikkim, Tripura, Arunachal Pradesh, Andaman & Nicobar, Chandigarh, Goa,
  Puducherry, Ladakh, Lakshadweep, Dadra & Nagar Haveli) — these have lower
  tender volume for this kind of work, lower priority, but ask me anytime.

Also worth checking occasionally: **GeM (gem.gov.in)** — mostly direct-purchase
listings rather than open tenders, but sometimes relevant items appear there too.

---

## One-time setup (about 20–25 minutes)

### Step 1 — Put this project on GitHub (free)

1. Go to https://github.com and sign up (free).
2. Click the **+** icon (top right) → **New repository**.
3. Name it something like `tender-alerts`. You can make it **Public** (simplest,
   tender info isn't sensitive) or Private — both work fine.
4. Click **Create repository**.
5. On the new repo's page, click **Add file → Upload files**, then drag in
   every file from this folder (including the hidden `.github` folder — if
   your drag-and-drop doesn't show it, use "choose your files" and select all).
6. Click **Commit changes**.

### Step 2 — Create a Gmail App Password (for sending alert emails)

1. Finish creating the new Gmail account you mentioned.
2. Go to https://myaccount.google.com/security
3. Turn on **2-Step Verification** if it isn't already on (required for app passwords).
4. Search for **"App passwords"** in the search bar at the top of that page.
5. Create one — name it "Tender Alerts" — and copy the 16-character password
   it shows you (no spaces). You won't be able to see it again, so paste it
   somewhere safe for the next step.

### Step 3 — Create your Telegram bot (free, 2 minutes)

1. Open Telegram, search for **@BotFather**, and start a chat with it.
2. Send `/newbot`, give it any name and a username ending in "bot" (e.g. `dad_tender_alert_bot`).
3. BotFather will reply with a **token** — a long string like `123456:ABC-...`. Copy it.
4. Now search for your new bot by its username and click **Start** (this is required —
   bots can't message you until you message them first).
5. Get your **Chat ID**: open this URL in your browser (replace `<TOKEN>` with your token):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   After messaging your bot in step 4, refresh that page — you'll see a number
   next to `"chat":{"id":` — that's your Chat ID. Copy it.

### Step 4 — Add your secrets to GitHub

1. In your GitHub repo, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret** and add each of these one at a time:

| Secret name | Value |
|---|---|
| `GMAIL_ADDRESS` | the new Gmail address |
| `GMAIL_APP_PASSWORD` | the 16-character app password from Step 2 |
| `ALERT_EMAILS` | `neeljain@hotmail.com,jainmohak@hotmail.com` |
| `TELEGRAM_BOT_TOKEN` | the token from BotFather |
| `TELEGRAM_CHAT_ID` | the chat ID you found |

### Step 5 — Test it

1. In your repo, click the **Actions** tab.
2. Click **Check Tenders** on the left, then **Run workflow** (top right).
3. Set "send_test_alert" to `true`, then click the green **Run workflow** button.
4. Wait ~30 seconds, refresh — you should get a test message by email and Telegram.
5. If it works: you're done! If not, click into the run to read the error log,
   and send it to me — I'll help debug it.

Once the test works, run the workflow **once more with "send_test_alert" set to
`false`** (or just leave it — the scheduled runs always use `false` automatically).
From here on, it runs by itself every 3 hours, forever, for free.

---

## Changing things later

- **Add/remove keywords:** open `check_tenders.py`, edit the `KEYWORDS` list near the top, commit the change.
- **Add a new state portal:** open `portals.json`, add a new entry with its name and app_url, commit. Ask me if you're not sure of the URL for a given state — I can look it up.
- **Change how often it checks:** edit the cron line in `.github/workflows/check-tenders.yml` (currently every 3 hours).
- **Add more email recipients:** update the `ALERT_EMAILS` secret (comma-separated).

## Honest limitations

- A few of the "best-effort" state portals above might have slightly different
  URLs by the time you set this up (government sites occasionally restructure).
  If the Actions log shows 0 results for a portal every single time, that's
  the sign — tell me and I'll fix it.
- The non-NIC states listed above (Gujarat, Karnataka, Telangana, AP, Delhi,
  Goa) need separate scraping logic I haven't built yet — happy to build one
  for any of them, just ask.
- This catches tenders the moment they're *published* on these portals. It
  can't catch tenders only announced via newspaper notice or word-of-mouth,
  which still happens sometimes for smaller municipal bodies.
