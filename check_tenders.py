"""
Tender Alert Checker
---------------------
Checks government e-procurement portals (CPPP + several state portals, all
running the NIC "GePNIC" software) for new tenders matching keywords, and
sends an alert by email + Telegram the moment a new match is found.

Designed to be run on a schedule by GitHub Actions (see
.github/workflows/check-tenders.yml), but can also be run manually:
    python check_tenders.py
"""

import json
import os
import re
import smtplib
import sys
import time
from email.mime.text import MIMEText
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# 1. SETTINGS — edit KEYWORDS here any time you want to add/remove search terms
# ---------------------------------------------------------------------------

KEYWORDS = [
    "High pressure Fog System for cooling",
    "Mist cooling system",
    "Misting system for cooling",
    "Musical fountain",
    "Musical Fountain with Multimedia",
]

STOP_WORDS = {"for", "with", "and", "the", "of", "a", "an", "to", "system", "systems"}

PORTALS_FILE = os.path.join(os.path.dirname(__file__), "portals.json")
STATE_FILE = os.path.join(os.path.dirname(__file__), "seen_tenders.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 25


# ---------------------------------------------------------------------------
# 2. KEYWORD MATCHING
# ---------------------------------------------------------------------------

def keyword_tokens(phrase):
    words = re.findall(r"[a-zA-Z]+", phrase.lower())
    return [w for w in words if w not in STOP_WORDS]


def find_matching_keyword(title):
    """Return the matched keyword string if `title` matches any keyword, else None."""
    title_lower = title.lower()
    for kw in KEYWORDS:
        if kw.lower() in title_lower:
            return kw
        tokens = keyword_tokens(kw)
        if tokens and all(tok in title_lower for tok in tokens):
            return kw
    return None


# ---------------------------------------------------------------------------
# 3. SCRAPING ONE PORTAL
# ---------------------------------------------------------------------------

def fetch_latest_tenders(portal):
    """
    Fetch the 'Latest Active Tenders' page for one portal and return a list of
    dicts: {title, url, portal_name, state}.
    Works for any portal running NIC's GePNIC software (CPPP + most states),
    since they all render tender links the same way: <a href="...DirectLink...">.
    """
    app_url = portal["app_url"]
    session = requests.Session()
    session.headers.update(HEADERS)

    results = []
    error = None
    diag = {}
    try:
        # The homepage itself shows a "Latest Tenders" widget with real entries.
        # Deep-linking straight to the "FrontEndLatestActiveTenders" page tends to
        # bounce back to a generic shell page on these session-based government
        # sites, so we read tenders directly off the homepage response instead.
        resp = session.get(app_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.find_all("a", href=lambda h: h and "DirectLink" in h)

        # Diagnostics in case we get 0 links, so we can tell what page we actually got.
        title_tag = soup.find("title")
        all_links = soup.find_all("a", href=True)
        sample_links = [
            {"text": a.get_text(strip=True)[:80], "href": a["href"][:120]}
            for a in all_links[:15]
        ]
        diag = {
            "final_url": resp.url,
            "status_code": resp.status_code,
            "html_length": len(resp.text),
            "page_title": title_tag.get_text(strip=True) if title_tag else None,
            "total_links_on_page": len(all_links),
            "sample_links": sample_links,
        }

        for link in links:
            title = link.get_text(strip=True)
            href = link.get("href")
            if not title or not href:
                continue
            full_url = urljoin(app_url, href)
            results.append({
                "title": title,
                "url": full_url,
                "portal_name": portal["name"],
                "state": portal["state"],
            })

    except Exception as exc:
        error = str(exc)
        print(f"  [warn] Could not check '{portal['name']}': {exc}")

    return results, error, diag


# ---------------------------------------------------------------------------
# 4. STATE (avoid duplicate alerts across runs)
# ---------------------------------------------------------------------------

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_seen(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, indent=2, ensure_ascii=False)


def tender_key(portal_name, title):
    return f"{portal_name}::{title.strip().lower()}"


def save_run_summary(summary):
    path = os.path.join(os.path.dirname(__file__), "last_run_summary.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 5. ALERTS
# ---------------------------------------------------------------------------

def build_message(matches):
    lines = [f"Found {len(matches)} new tender(s) matching your keywords:\n"]
    for m in matches:
        lines.append(f"• [{m['state']}] {m['title']}")
        lines.append(f"  Matched keyword: {m['matched_keyword']}")
        lines.append(f"  Link: {m['url']}\n")
    return "\n".join(lines)


def send_email(subject, body):
    gmail_address = os.environ.get("GMAIL_ADDRESS")
    gmail_app_password = os.environ.get("GMAIL_APP_PASSWORD")
    alert_emails = os.environ.get("ALERT_EMAILS", "")

    if not (gmail_address and gmail_app_password and alert_emails):
        print("  [warn] Email not configured (missing secrets) — skipping email alert.")
        return

    recipients = [e.strip() for e in alert_emails.split(",") if e.strip()]
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = ", ".join(recipients)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=REQUEST_TIMEOUT) as server:
            server.login(gmail_address, gmail_app_password)
            server.sendmail(gmail_address, recipients, msg.as_string())
        print(f"  Email sent to: {', '.join(recipients)}")
    except Exception as exc:
        print(f"  [error] Failed to send email: {exc}")


def send_telegram(body):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not (token and chat_id):
        print("  [warn] Telegram not configured (missing secrets) — skipping Telegram alert.")
        return

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": body},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code == 200:
            print("  Telegram message sent.")
        else:
            print(f"  [error] Telegram API error: {resp.status_code} {resp.text}")
    except Exception as exc:
        print(f"  [error] Failed to send Telegram message: {exc}")


# ---------------------------------------------------------------------------
# 6. MAIN
# ---------------------------------------------------------------------------

def main():
    # Optional: send a one-off test alert to confirm email/Telegram are wired up,
    # without needing a real tender match. Triggered by setting SEND_TEST_ALERT=true.
    if os.environ.get("SEND_TEST_ALERT", "").lower() == "true":
        test_body = (
            "This is a test alert from your tender checker.\n"
            "If you received this by email and/or Telegram, the setup works!"
        )
        print("Sending test alert...")
        send_email("Tender Alert System - Test Message", test_body)
        send_telegram(test_body)
        return

    with open(PORTALS_FILE, "r", encoding="utf-8") as f:
        portals = json.load(f)["portals"]

    seen = load_seen()
    new_matches = []
    portal_summary = []

    for portal in portals:
        print(f"Checking: {portal['name']} ...")
        tenders, error, diag = fetch_latest_tenders(portal)
        print(f"  Found {len(tenders)} listed tender(s).")
        entry = {
            "name": portal["name"],
            "state": portal["state"],
            "tenders_seen": len(tenders),
            "status": "ok" if len(tenders) > 0 else (error or "0 results (check URL / site structure)"),
        }
        entry["sample_titles"] = [t["title"][:90] for t in tenders[:3]]
        if len(tenders) == 0 and diag:
            entry["diagnostic"] = diag
        portal_summary.append(entry)

        for tender in tenders:
            kw = find_matching_keyword(tender["title"])
            if not kw:
                continue

            key = tender_key(tender["portal_name"], tender["title"])
            if key in seen:
                continue  # already alerted before

            tender["matched_keyword"] = kw
            new_matches.append(tender)
            seen[key] = True

        time.sleep(1)  # be polite to government servers

    if new_matches:
        print(f"\n{len(new_matches)} new matching tender(s) found. Sending alerts...")
        body = build_message(new_matches)
        send_email(f"{len(new_matches)} New Tender Alert(s) - Musical Fountain / Misting", body)
        send_telegram(body)
    else:
        print("\nNo new matching tenders this run.")

    save_seen(seen)
    save_run_summary({
        "checked_at_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "portals": portal_summary,
        "new_matches_found": len(new_matches),
    })


if __name__ == "__main__":
    sys.exit(main())
