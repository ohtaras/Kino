"""
Kino Allwyn.gr - Statistical Analysis Engine
Συχνότητες, hot/cold numbers, gap analysis, positional bias.
"""

from collections import Counter, defaultdict
from typing import Callable
import math
import random


TOTAL_NUMBERS = 80
DRAW_SIZE = 20


# ---------------------------------------------------------------------------
# Βασικές στατιστικές
# ---------------------------------------------------------------------------

def frequency_map(draws: list[list[int]]) -> dict[int, int]:
    """Συχνότητα εμφάνισης κάθε αριθμού σε όλες τις κληρώσεις."""
    counter: Counter = Counter()
    for draw in draws:
        counter.update(draw)
    return dict(counter)


def expected_frequency(draws: list[list[int]]) -> float:
    """Αναμενόμενη συχνότητα για κάθε αριθμό (DRAW_SIZE / TOTAL_NUMBERS * #draws)."""
    return len(draws) * DRAW_SIZE / TOTAL_NUMBERS


def hot_numbers(freq: dict[int, int], top_n: int = 20) -> list[int]:
    """Οι πιο συχνοί αριθμοί (hot)."""
    return [n for n, _ in sorted(freq.items(), key=lambda x: -x[1])][:top_n]


def cold_numbers(freq: dict[int, int], top_n: int = 20) -> list[int]:
    """Οι λιγότερο συχνοί αριθμοί (cold/overdue)."""
    return [n for n, _ in sorted(freq.items(), key=lambda x: x[1])][:top_n]


# ---------------------------------------------------------------------------
# Gap / Delay analysis
# ---------------------------------------------------------------------------

def gap_analysis(draws: list[list[int]]) -> dict[int, int]:
    """
    Για κάθε αριθμό: πόσες κληρώσεις πέρασαν από την τελευταία εμφάνισή του.
    Μεγαλύτερο gap = πιο «οφειλόμενος».
    """
    last_seen: dict[int, int] = {}
    for draw_idx, draw in enumerate(draws):
        for num in draw:
            last_seen[num] = draw_idx

    total_draws = len(draws)
    gaps = {}
    for n in range(1, TOTAL_NUMBERS + 1):
        if n in last_seen:
            gaps[n] = total_draws - 1 - last_seen[n]
        else:
            gaps[n] = total_draws  # Δεν εμφανίστηκε ποτέ
    return gaps


# ---------------------------------------------------------------------------
# Decade / zone analysis
# ---------------------------------------------------------------------------

def decade_weights(draws: list[list[int]]) -> dict[int, float]:
    """
    Βάρος για κάθε δεκάδα (1-10, 11-20, ... 71-80).
    Επιστρέφει normalized weights (sum=1).
    """
    decade_count: Counter = Counter()
    for draw in draws:
        for n in draw:
            decade_count[(n - 1) // 10] += 1
    total = sum(decade_count.values()) or 1
    return {d: count / total for d, count in decade_count.items()}


# ---------------------------------------------------------------------------
# Scoring function
# ---------------------------------------------------------------------------

def score_numbers(
    draws: list[list[int]],
    freq_weight: float = 0.35,
    gap_weight: float = 0.35,
    decade_weight: float = 0.30,
) -> dict[int, float]:
    """
    Υπολογίζει σύνθετο score για κάθε αριθμό 1-80.
    Συνδυάζει: συχνότητα, gap (οφειλόμενοι), και decade balance.
    """
    freq = frequency_map(draws)
    gaps = gap_analysis(draws)
    dw = decade_weights(draws)

    # Normalize συχνότητες (0..1)
    max_freq = max(freq.values()) if freq else 1
    min_freq = min(freq.values()) if freq else 0
    freq_range = max_freq - min_freq or 1

    # Normalize gaps (0..1) — μεγαλύτερο gap = υψηλότερο score
    max_gap = max(gaps.values()) if gaps else 1

    scores: dict[int, float] = {}
    for n in range(1, TOTAL_NUMBERS + 1):
        f = freq.get(n, 0)
        g = gaps.get(n, len(draws))
        decade = (n - 1) // 10
        dw_score = dw.get(decade, DRAW_SIZE / TOTAL_NUMBERS)

        # Normalized scores
        freq_score = (f - min_freq) / freq_range  # high freq = high score
        gap_score = g / max_gap                    # high gap = high score
        # decade: τιμωρούμε τις δεκάδες που ήδη έχουν πολλές εμφανίσεις
        decade_score = 1.0 - min(dw_score * 10, 1.0)

        scores[n] = (
            freq_weight * freq_score
            + gap_weight * gap_score
            + decade_weight * decade_score
        )

    return scores


# ---------------------------------------------------------------------------
# Επιλογή αριθμών
# ---------------------------------------------------------------------------

def pick_numbers(
    scores: dict[int, float],
    n: int = 9,
    randomness: float = 0.20,
    seed: int | None = None,
) -> list[int]:
    """
    Επιλέγει N αριθμούς βάσει scores με μικρό ποσοστό τυχαιότητας.

    Args:
        scores:     Score για κάθε αριθμό.
        n:          Πόσους αριθμούς να επιλέξει.
        randomness: 0=καθαρά deterministic, 1=καθαρά τυχαίο.
        seed:       Για reproducibility.
    """
    rng = random.Random(seed)

    # Προσθέτουμε τυχαίο θόρυβο στα scores
    noisy: dict[int, float] = {
        num: score + rng.uniform(0, randomness)
        for num, score in scores.items()
    }

    # Weighted random sample χωρίς επανάληψη
    numbers = list(noisy.keys())
    weights = [max(noisy[num], 0.001) for num in numbers]

    selected = []
    remaining_numbers = numbers[:]
    remaining_weights = weights[:]

    for _ in range(min(n, len(remaining_numbers))):
        total = sum(remaining_weights)
        r = rng.uniform(0, total)
        cumulative = 0
        for i, w in enumerate(remaining_weights):
            cumulative += w
            if r <= cumulative:
                selected.append(remaining_numbers[i])
                remaining_numbers.pop(i)
                remaining_weights.pop(i)
                break

    return sorted(selected)


# ---------------------------------------------------------------------------
# Fallback: Purely statistical (χωρίς ιστορικά δεδομένα)
# ---------------------------------------------------------------------------

def statistical_pick(n: int = 9, seed: int | None = None) -> list[int]:
    """
    Επιλογή βάσει μαθηματικής κατανομής όταν δεν υπάρχουν ιστορικά δεδομένα.
    Χρησιμοποιεί balanced sampling: σε κάθε δεκάδα (1-80) προσπαθεί
    να πάρει ~n/8 αριθμούς, με μικρή τυχαιότητα.
    """
    rng = random.Random(seed)
    decades = list(range(8))  # 0..7 → 1-10, 11-20, ... 71-80

    # Βάρη δεκάδων: ελαφρά προτίμηση στη μέση (20-60)
    decade_weights_list = []
    for d in decades:
        mid = d * 10 + 5.5
        weight = 1.0 - 0.3 * abs(mid - 40.5) / 40.5
        decade_weights_list.append(weight)

    picks = set()
    attempts = 0
    while len(picks) < n and attempts < 1000:
        attempts += 1
        # Επέλεξε δεκάδα
        total_dw = sum(decade_weights_list)
        r = rng.uniform(0, total_dw)
        cumulative = 0
        chosen_decade = 0
        for d, w in enumerate(decade_weights_list):
            cumulative += w
            if r <= cumulative:
                chosen_decade = d
                break
        # Επέλεξε αριθμό μέσα στη δεκάδα
        lo = chosen_decade * 10 + 1
        hi = lo + 9
        candidate = rng.randint(lo, hi)
        picks.add(candidate)

    return sorted(picks)[:n]


# ---------------------------------------------------------------------------
# Στατιστικά report
# ---------------------------------------------------------------------------

def print_stats(draws: list[list[int]], scores: dict[int, float]) -> None:
    """Εκτυπώνει σύνοψη στατιστικών."""
    freq = frequency_map(draws)
    gaps = gap_analysis(draws)
    exp = expected_frequency(draws)

    print(f"\n{'='*50}")
    print(f"  ΣΤΑΤΙΣΤΙΚΑ KINO ({len(draws)} κληρώσεις)")
    print(f"{'='*50}")
    print(f"  Αναμενόμενη συχνότητα / αριθμό: {exp:.1f}")
    print(f"\n  TOP 10 HOT  : {hot_numbers(freq, 10)}")
    print(f"  TOP 10 COLD : {cold_numbers(freq, 10)}")

    # Top 5 οφειλόμενοι
    overdue = sorted(gaps.items(), key=lambda x: -x[1])[:5]
    print(f"  TOP 5 OVERDUE: {[n for n, _ in overdue]}")
    print(f"{'='*50}\n")
