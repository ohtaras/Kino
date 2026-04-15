"""
Kino Allwyn.gr - Data Fetcher
Αντλεί αποτελέσματα και στατιστικά από το OPAP API (game ID: 1100)

Endpoints που χρησιμοποιούνται:
  GET /draws/v3.0/1100/last/{limit}
  GET /draws/v3.0/1100/draw-date/{fromDate}/{toDate}
  GET /draws/v3.0/1100/upcoming/1
  GET /games/v1.0/1100/statistics?drawRange={n}
"""

import urllib.request
import urllib.error
import json
import time
from datetime import datetime, timedelta

GAME_ID = 1100
DRAWS_BASE = "https://api.opap.gr/draws/v3.0"
GAMES_BASE = "https://api.opap.gr/games/v1.0"


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _fetch(url: str, retries: int = 4) -> dict | list | None:
    """GET request με retry + exponential backoff."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, headers=headers)
    delay = 2
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"[!] HTTP {e.code} για {url}")
            return None
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                print(f"[!] Σφάλμα σύνδεσης ({e.reason}), επανάληψη σε {delay}s…")
                time.sleep(delay)
                delay *= 2
            else:
                print(f"[!] Αδυναμία σύνδεσης μετά από {retries} προσπάθειες: {e}")
    return None


# ---------------------------------------------------------------------------
# Draw endpoints
# ---------------------------------------------------------------------------

def get_last_draws(limit: int = 200) -> list[dict]:
    """Τελευταίες {limit} κληρώσεις Kino."""
    url = f"{DRAWS_BASE}/{GAME_ID}/last/{limit}"
    data = _fetch(url)
    if data is None:
        return []
    return data if isinstance(data, list) else data.get("content", [])


def get_draws_by_date(date_from: str, date_to: str) -> list[dict]:
    """Κληρώσεις μεταξύ δύο ημερομηνιών (format: YYYY-MM-DD)."""
    url = f"{DRAWS_BASE}/{GAME_ID}/draw-date/{date_from}/{date_to}"
    data = _fetch(url)
    if data is None:
        return []
    return data if isinstance(data, list) else data.get("content", [])


def get_upcoming_draw() -> dict | None:
    """Επόμενη προγραμματισμένη κλήρωση."""
    url = f"{DRAWS_BASE}/{GAME_ID}/upcoming/1"
    return _fetch(url)


def get_active_draw() -> dict | None:
    """Τρέχουσα ενεργή κλήρωση."""
    url = f"{DRAWS_BASE}/{GAME_ID}/active"
    return _fetch(url)


# ---------------------------------------------------------------------------
# Statistics endpoint
# ---------------------------------------------------------------------------

def get_statistics(draw_range: int = 1801) -> list[dict] | None:
    """
    Στατιστικά Kino για τις τελευταίες {draw_range} κληρώσεις.
    Επιστρέφει λίστα εγγραφών: [{number, occurrences, lastDraw, minGap, maxGap}, ...]
    """
    url = f"{GAMES_BASE}/{GAME_ID}/statistics?drawRange={draw_range}"
    data = _fetch(url)
    if data is None:
        return None
    # Το API μπορεί να επιστρέψει {"statistics": [...]} ή απευθείας λίστα
    if isinstance(data, list):
        return data
    for key in ("statistics", "numberStatistics", "results", "content"):
        if key in data and isinstance(data[key], list):
            return data[key]
    return None


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def extract_numbers(draw: dict) -> list[int] | None:
    """Εξάγει τα 20 κληρωθέντα νούμερα από ένα draw object."""
    try:
        wn = draw.get("winningNumbers") or {}
        # Δομή: {"list": [...], "bonus": [...]}
        nums = wn.get("list") or wn.get("numbers") or []
        if not nums:
            # Fallback: flat fields
            nums = draw.get("numbers") or draw.get("drawnNumbers") or []
        if nums and len(nums) == 20:
            return sorted(int(n) for n in nums)
        return None
    except (TypeError, ValueError, KeyError):
        return None


def parse_statistics(stats: list[dict]) -> dict[int, dict]:
    """
    Μετατρέπει τη λίστα στατιστικών σε dict:
    { number: {occurrences, lastDraw, minGap, maxGap} }
    """
    result = {}
    for entry in stats:
        num = entry.get("number") or entry.get("num")
        if num is None:
            continue
        result[int(num)] = {
            "occurrences": entry.get("occurrences", 0),
            "lastDraw":    entry.get("lastDraw", 0),    # κληρώσεις πριν εμφανιστεί τελευταία
            "minGap":      entry.get("minGap", 0),
            "maxGap":      entry.get("maxGap", 0),
        }
    return result


# ---------------------------------------------------------------------------
# High-level loaders
# ---------------------------------------------------------------------------

def load_draws(limit: int = 200) -> list[list[int]]:
    """
    Φορτώνει τις τελευταίες {limit} κληρώσεις.
    Επιστρέφει λίστα από λίστες 20 νούμερων.
    """
    print(f"[*] Φόρτωση {limit} τελευταίων κληρώσεων…")
    raw = get_last_draws(limit)
    draws = [n for d in raw if (n := extract_numbers(d)) is not None]
    print(f"[+] {len(draws)} έγκυρες κληρώσεις.")
    return draws


def load_draws_by_date(days: int = 30) -> list[list[int]]:
    """Φορτώνει κληρώσεις των τελευταίων {days} ημερών."""
    date_to   = datetime.now().strftime("%Y-%m-%d")
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"[*] Φόρτωση κληρώσεων {date_from} → {date_to}…")
    raw = get_draws_by_date(date_from, date_to)
    draws = [n for d in raw if (n := extract_numbers(d)) is not None]
    print(f"[+] {len(draws)} έγκυρες κληρώσεις.")
    return draws


def load_statistics(draw_range: int = 1801) -> dict[int, dict] | None:
    """
    Φορτώνει προ-επεξεργασμένα στατιστικά από το OPAP API.
    Πολύ αποδοτικό: 1 request αντί για εκατοντάδες.
    """
    print(f"[*] Φόρτωση στατιστικών ({draw_range} κληρώσεις)…")
    raw = get_statistics(draw_range)
    if raw is None:
        print("[!] Δεν ήταν δυνατή η φόρτωση στατιστικών.")
        return None
    stats = parse_statistics(raw)
    print(f"[+] Στατιστικά για {len(stats)} αριθμούς.")
    return stats


if __name__ == "__main__":
    draws = load_draws(limit=50)
    if draws:
        print(f"Τελευταία κλήρωση: {draws[0]}")

    stats = load_statistics(draw_range=1801)
    if stats:
        top5 = sorted(stats.items(), key=lambda x: -x[1]["occurrences"])[:5]
        print(f"Top 5 hot: {[n for n, _ in top5]}")
