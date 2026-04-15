#!/usr/bin/env python3
"""
Kino Allwyn.gr - Predictor
Πρόβλεψη 9 αριθμών για την επόμενη κλήρωση.

Χρήση:
    python predict.py              # 9 αριθμοί (default)
    python predict.py --count 9   # ορισμός πλήθους
    python predict.py --days 60   # ιστορικό 60 ημερών
    python predict.py --seed 42   # αναπαραγώγιμο αποτέλεσμα
    python predict.py --stats      # εμφάνιση στατιστικών
"""

import argparse
import random
import sys
from datetime import datetime

from fetch_data import load_draws
from analysis import score_numbers, pick_numbers, statistical_pick, print_stats


def banner() -> None:
    print("=" * 52)
    print("   KINO ALLWYN.GR — Σύστημα Πρόβλεψης")
    print(f"   {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 52)


def predict(count: int = 9, days: int = 60, seed: int | None = None, show_stats: bool = False) -> list[int]:
    """
    Κύρια ρουτίνα πρόβλεψης.
    1. Φορτώνει ιστορικά δεδομένα από OPAP API
    2. Υπολογίζει σύνθετα scores
    3. Επιλέγει τους καλύτερους N αριθμούς
    """
    banner()

    draws = load_draws(days=days)

    if len(draws) >= 5:
        scores = score_numbers(draws)
        if show_stats:
            print_stats(draws, scores)
        numbers = pick_numbers(scores, n=count, seed=seed)
        method = f"Στατιστική ανάλυση ({len(draws)} κληρώσεων)"
    else:
        print("[!] Ανεπαρκή ιστορικά δεδομένα — χρήση μαθηματικής κατανομής.")
        if seed is None:
            seed = int(datetime.now().timestamp())
        numbers = statistical_pick(n=count, seed=seed)
        method = "Μαθηματική κατανομή (fallback)"

    print(f"\n  Μέθοδος  : {method}")
    print(f"  Αριθμοί  : {count}")
    print()
    print("  ┌─────────────────────────────────────┐")
    print(f"  │  ΠΡΟΒΛΕΨΗ ΕΠΟΜΕΝΗΣ ΚΛΗΡΩΣΗΣ KINO   │")
    print("  ├─────────────────────────────────────┤")

    # Εμφάνιση σε γραμμές των 3
    row = []
    for i, n in enumerate(numbers, 1):
        row.append(f"  {n:>2}")
        if i % 3 == 0 or i == len(numbers):
            print("  │  " + "   ".join(row) + " " * (3 - len(row)) * 6 + "    │")
            row = []

    print("  └─────────────────────────────────────┘")
    print(f"\n  {' — '.join(str(n) for n in numbers)}")
    print()
    print("  * Η πρόβλεψη βασίζεται σε στατιστική ανάλυση.")
    print("  * Το Kino είναι τυχαίο παιχνίδι — δεν υπάρχει εγγύηση.")
    print("=" * 52)

    return numbers


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kino Allwyn.gr — Πρόβλεψη επόμενης κλήρωσης"
    )
    parser.add_argument(
        "--count", "-c",
        type=int, default=9,
        help="Πόσους αριθμούς να προβλέψει (default: 9)"
    )
    parser.add_argument(
        "--days", "-d",
        type=int, default=60,
        help="Ιστορικό ημερών για ανάλυση (default: 60)"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int, default=None,
        help="Seed για αναπαραγώγιμα αποτελέσματα"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Εμφάνιση αναλυτικών στατιστικών"
    )

    args = parser.parse_args()

    if not (1 <= args.count <= 20):
        print("[!] Ο αριθμός επιλογών πρέπει να είναι μεταξύ 1 και 20.")
        sys.exit(1)

    predict(
        count=args.count,
        days=args.days,
        seed=args.seed,
        show_stats=args.stats,
    )


if __name__ == "__main__":
    main()
