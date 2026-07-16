#!/usr/bin/env python3
"""CROUS watcher — one-shot run for GitHub Actions."""
import os, re, json, sys, requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SEARCHES = {
    "Nanterre": "https://trouverunlogement.lescrous.fr/tools/47/search?bounds=2.169302_48.9205991_2.234232_48.8742291&locationName=Nanterre+%2892000%29",
    "Île-de-France": "https://trouverunlogement.lescrous.fr/tools/47/search?occupationModes=alone&bounds=1.4462445_49.241431_3.5592208_48.1201456&locationName=Île-de-France",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
STATE_FILE = "state.json"


def send_telegram(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Telegram token or chat ID is empty — check GitHub Secrets.")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15)
    r.raise_for_status()


def check_status(url):
    """Return 'empty', 'available', or 'unknown'."""
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    html = r.text

    # Did we actually reach a CROUS search page? If not, don't guess.
    if "Trouver un logement" not in html:
        return "unknown"

    # The page title carries "page X sur Y". Empty => "page 0 sur 0".
    m = re.search(r"page\s+(\d+)\s+sur\s+(\d+)", html)
    if m:
        total = int(m.group(2))
        return "available" if total > 0 else "empty"

    # Fallback to the sentence if the title format ever changes.
    if "Aucun logement trouvé" in html:
        return "empty"

    return "unknown"


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main():
    state = load_state()
    changed = False

    for name, url in SEARCHES.items():
        try:
            status = check_status(url)
        except Exception as e:
            print(f"[{name}] fetch error: {e}", file=sys.stderr)
            continue

        was_available = state.get(name, False)
        available = (status == "available")
        print(f"[{name}] status={status} (was_available={was_available})")

        if status == "unknown":
            continue  # weird page — no alert, no state change

        if available and not was_available:
            send_telegram(f"🏠 LOGEMENT DISPONIBLE — {name} !\n\n{url}")
            print(f"[{name}] ALERT SENT")

        if available != was_available:
            state[name] = available
            changed = True

    if changed:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
        print("State updated.")
    else:
        print("No change.")


if __name__ == "__main__":
    main()