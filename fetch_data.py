"""
Kino Allwyn.gr - Data Fetcher
Αντλεί ιστορικά αποτελέσματα από το OPAP API (game ID: 1100)
"""

import urllib.request
import urllib.error
import json
import time
from datetime import datetime, timedelta


GAME_ID = 1100
BASE_URL = "https://api.opap.gr/draws/v3.0"


def fetch_url(url: str, retries: int = 3) -> dict | None:
    """Κάνει GET request με retry logic."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                print(f"[!] Αδυναμία σύνδεσης: {e}")
                return None
    return None


def get_last_draw() -> dict | None:
    """Επιστρέφει την τελευταία κλήρωση και την ενεργή."""
    url = f"{BASE_URL}/{GAME_ID}/last-result-and-active"
    return fetch_url(url)


def get_draws_by_date(date_from: str, date_to: str) -> list[dict]:
    """
    Επιστρέφει κληρώσεις μεταξύ δύο ημερομηνιών (YYYY-MM-DD).
    Χρησιμοποιεί το endpoint: /draws/v3.0/{gameId}/draw-date/{dateFrom}/{dateTo}
    """
    url = f"{BASE_URL}/{GAME_ID}/draw-date/{date_from}/{date_to}"
    data = fetch_url(url)
    if data is None:
        return []
    # API επιστρέφει είτε list είτε {"content": [...]}
    if isinstance(data, list):
        return data
    return data.get("content", [])


def get_recent_draws(days: int = 30) -> list[dict]:
    """Επιστρέφει κληρώσεις των τελευταίων N ημερών."""
    date_to = datetime.now().strftime("%Y-%m-%d")
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    return get_draws_by_date(date_from, date_to)


def extract_numbers(draw: dict) -> list[int] | None:
    """Εξάγει τα κληρωθέντα νούμερα από ένα draw object."""
    try:
        result = draw.get("result") or draw.get("drawResults") or {}
        winningNumbers = (
            result.get("winningNumbers")
            or result.get("drawnNumbers")
            or draw.get("winningNumbers")
            or []
        )
        if winningNumbers:
            return sorted([int(n) for n in winningNumbers])
        return None
    except (TypeError, ValueError, KeyError):
        return None


def load_draws(days: int = 60) -> list[list[int]]:
    """
    Φορτώνει ιστορικά δεδομένα. Επιστρέφει λίστα από λίστες νούμερων.
    """
    print(f"[*] Φόρτωση κληρώσεων των τελευταίων {days} ημερών...")
    raw = get_recent_draws(days)
    draws = []
    for draw in raw:
        numbers = extract_numbers(draw)
        if numbers and len(numbers) == 20:
            draws.append(numbers)

    if not draws:
        # Δοκιμάζουμε το last-result endpoint
        last = get_last_draw()
        if last:
            for key in ("lastResult", "lastDraw", "result"):
                candidate = last.get(key)
                if isinstance(candidate, dict):
                    numbers = extract_numbers(candidate)
                    if numbers:
                        draws.append(numbers)
                        break
            # Μερικές φορές το last-result επιστρέφει απευθείας numbers
            numbers = extract_numbers(last)
            if numbers:
                draws.append(numbers)

    print(f"[+] Βρέθηκαν {len(draws)} κληρώσεις.")
    return draws


if __name__ == "__main__":
    draws = load_draws(days=30)
    if draws:
        print(f"Τελευταία κλήρωση: {draws[-1]}")
    else:
        print("Δεν βρέθηκαν δεδομένα.")
