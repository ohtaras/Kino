#!/usr/bin/env python3
"""
Kino Allwyn.gr - Predictor
Πρόβλεψη N αριθμών για την επόμενη κλήρωση.

Χρήση:
    python predict.py              # 9 αριθμοί (default)
    python predict.py --count 12  # ορισμός πλήθους
    python predict.py --draws 200 # χρήση raw draws αντί statistics
    python predict.py --stats     # εμφάνιση στατιστικών
    python predict.py --seed 42   # αναπαραγώγιμο αποτέλεσμα
"""

import argparse
import sys
from datetime import datetime

from fetch_data import load_statistics, load_draws
from analysis import (
    score_from_statistics,
    score_from_draws,
    pick_numbers,
    statistical_pick,
    print_stats_from_api,
    print_stats_from_draws,
)


def banner() -> None:
    print("=" * 54)
    print("   KINO ALLWYN.GR — Σύστημα Πρόβλεψης")
    print(f"   {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 54)


def predict(
    count: int = 9,
    draw_range: int = 1801,
    use_raw_draws: int = 0,
    seed: int | None = None,
    show_stats: bool = False,
) -> list[int]:
    """
    Κύρια ρουτίνα πρόβλεψης.
    Στρατηγική (προτεραιότητα):
      1. OPAP Statistics API  (drawRange κληρώσεις — ένα request)
      2. Raw draws            (αν ζητηθεί ή αποτύχει το statistics)
      3. Μαθηματική κατανομή (fallback χωρίς δεδομένα)
    """
    banner()

    numbers: list[int] = []
    method = ""

    # --- Στρατηγική 1: OPAP statistics ---
    if not use_raw_draws:
        stats = load_statistics(draw_range=draw_range)
        if stats and len(stats) >= 70:
            scores = score_from_statistics(stats)
            if show_stats:
                print_stats_from_api(stats)
            numbers = pick_numbers(scores, n=count, seed=seed)
            method  = f"OPAP Statistics API ({draw_range} κληρώσεις)"

    # --- Στρατηγική 2: Raw draws ---
    if not numbers:
        limit = use_raw_draws if use_raw_draws else 200
        draws = load_draws(limit=limit)
        if len(draws) >= 10:
            scores = score_from_draws(draws)
            if show_stats:
                print_stats_from_draws(draws)
            numbers = pick_numbers(scores, n=count, seed=seed)
            method  = f"Ανάλυση raw draws ({len(draws)} κληρώσεις)"

    # --- Στρατηγική 3: Fallback ---
    if not numbers:
        print("[!] Χωρίς δεδομένα — χρήση μαθηματικής κατανομής.")
        if seed is None:
            seed = int(datetime.now().timestamp())
        numbers = statistical_pick(n=count, seed=seed)
        method  = "Μαθηματική κατανομή (fallback)"

    # --- Εκτύπωση αποτελέσματος ---
    print(f"\n  Μέθοδος : {method}")
    print(f"  Αριθμοί : {count}")
    print()
    print("  ┌───────────────────────────────────────┐")
    print("  │   ΠΡΟΒΛΕΨΗ ΕΠΟΜΕΝΗΣ ΚΛΗΡΩΣΗΣ KINO    │")
    print("  ├───────────────────────────────────────┤")

    row: list[str] = []
    for i, n in enumerate(numbers, 1):
        row.append(f"{n:>3}")
        if i % 3 == 0 or i == len(numbers):
            padding = "   " * (3 - len(row))
            print(f"  │   {'  '.join(row)}{padding}              │")
            row = []

    print("  └───────────────────────────────────────┘")
    print()
    print(f"  {' — '.join(str(n) for n in numbers)}")
    print()
    print("  * Βασίζεται σε στατιστική ανάλυση ιστορικών δεδομένων.")
    print("  * Το Kino είναι τυχαίο — καμία εγγύηση αποτελέσματος.")
    print("=" * 54)

    return numbers


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kino Allwyn.gr — Πρόβλεψη επόμενης κλήρωσης"
    )
    parser.add_argument("--count",  "-c", type=int, default=9,
                        help="Πόσοι αριθμοί (default: 9)")
    parser.add_argument("--range",  "-r", type=int, default=1801,
                        help="drawRange για statistics endpoint (default: 1801)")
    parser.add_argument("--draws",  "-d", type=int, default=0,
                        help="Χρήση raw draws αντί statistics (δώσε limit)")
    parser.add_argument("--seed",   "-s", type=int, default=None,
                        help="Seed για αναπαραγώγιμα αποτελέσματα")
    parser.add_argument("--stats",  action="store_true",
                        help="Εμφάνιση αναλυτικών στατιστικών")
    args = parser.parse_args()

    if not (1 <= args.count <= 20):
        print("[!] Ο αριθμός επιλογών πρέπει να είναι 1–20.")
        sys.exit(1)

    predict(
        count=args.count,
        draw_range=args.range,
        use_raw_draws=args.draws,
        seed=args.seed,
        show_stats=args.stats,
    )


if __name__ == "__main__":
    main()
