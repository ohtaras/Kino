"""
Kino Allwyn.gr - Statistical Analysis Engine
Συχνότητες, hot/cold, gap analysis, positional bias.
Υποστηρίζει τόσο raw draws όσο και προ-επεξεργασμένα OPAP statistics.
"""

from collections import Counter
import random

TOTAL_NUMBERS = 80
DRAW_SIZE = 20


# ---------------------------------------------------------------------------
# Από raw draws
# ---------------------------------------------------------------------------

def frequency_map(draws: list[list[int]]) -> dict[int, int]:
    counter: Counter = Counter()
    for draw in draws:
        counter.update(draw)
    return {n: counter.get(n, 0) for n in range(1, TOTAL_NUMBERS + 1)}


def gap_analysis(draws: list[list[int]]) -> dict[int, int]:
    """Πόσες κληρώσεις πέρασαν από την τελευταία εμφάνιση κάθε αριθμού."""
    last_seen: dict[int, int] = {}
    for idx, draw in enumerate(draws):
        for num in draw:
            last_seen[num] = idx
    total = len(draws)
    return {
        n: (total - 1 - last_seen[n]) if n in last_seen else total
        for n in range(1, TOTAL_NUMBERS + 1)
    }


def decade_weights(draws: list[list[int]]) -> dict[int, float]:
    decade_count: Counter = Counter()
    for draw in draws:
        for n in draw:
            decade_count[(n - 1) // 10] += 1
    total = sum(decade_count.values()) or 1
    return {d: c / total for d, c in decade_count.items()}


# ---------------------------------------------------------------------------
# Score από raw draws
# ---------------------------------------------------------------------------

def score_from_draws(
    draws: list[list[int]],
    freq_weight: float = 0.35,
    gap_weight: float = 0.35,
    decade_weight: float = 0.30,
) -> dict[int, float]:
    freq  = frequency_map(draws)
    gaps  = gap_analysis(draws)
    dw    = decade_weights(draws)

    max_freq = max(freq.values()) or 1
    min_freq = min(freq.values())
    freq_range = max_freq - min_freq or 1
    max_gap  = max(gaps.values()) or 1

    scores: dict[int, float] = {}
    for n in range(1, TOTAL_NUMBERS + 1):
        freq_score   = (freq[n] - min_freq) / freq_range
        gap_score    = gaps[n] / max_gap
        decade       = (n - 1) // 10
        decade_score = 1.0 - min(dw.get(decade, DRAW_SIZE / TOTAL_NUMBERS) * 10, 1.0)

        scores[n] = (
            freq_weight   * freq_score
            + gap_weight  * gap_score
            + decade_weight * decade_score
        )
    return scores


# ---------------------------------------------------------------------------
# Score από OPAP statistics (occurrences, lastDraw, minGap, maxGap)
# ---------------------------------------------------------------------------

def score_from_statistics(
    stats: dict[int, dict],
    freq_weight: float = 0.35,
    gap_weight: float = 0.40,
    spread_weight: float = 0.25,
) -> dict[int, float]:
    """
    Υπολογίζει scores από τα προ-επεξεργασμένα OPAP statistics.

    stats format: { number: {occurrences, lastDraw, minGap, maxGap} }
      - occurrences : συνολικές εμφανίσεις στο drawRange
      - lastDraw    : κληρώσεις πριν από την τελευταία εμφάνιση (0 = εμφανίστηκε στην τελευταία)
      - minGap      : ελάχιστο κενό μεταξύ εμφανίσεων
      - maxGap      : μέγιστο κενό μεταξύ εμφανίσεων
    """
    occ     = {n: s["occurrences"] for n, s in stats.items()}
    last_d  = {n: s["lastDraw"]    for n, s in stats.items()}
    max_gap = {n: s["maxGap"]      for n, s in stats.items()}

    max_occ    = max(occ.values())    or 1
    min_occ    = min(occ.values())
    occ_range  = max_occ - min_occ    or 1
    max_last   = max(last_d.values()) or 1
    max_maxgap = max(max_gap.values()) or 1

    scores: dict[int, float] = {}
    for n in range(1, TOTAL_NUMBERS + 1):
        s = stats.get(n, {})
        o  = s.get("occurrences", 0)
        ld = s.get("lastDraw", max_last)
        mg = s.get("maxGap", 0)

        # Freq score: αριθμοί με πάνω από μέση συχνότητα παίρνουν bonus
        freq_score = (o - min_occ) / occ_range

        # Gap score: αριθμοί που δεν εμφανίστηκαν πρόσφατα = υψηλότερο score
        gap_score = ld / max_last

        # Spread score: αριθμοί με μεγάλο maxGap είναι πιο «ώριμοι» να εμφανιστούν
        spread_score = mg / max_maxgap

        scores[n] = (
            freq_weight    * freq_score
            + gap_weight   * gap_score
            + spread_weight * spread_score
        )

    return scores


# ---------------------------------------------------------------------------
# Επιλογή αριθμών (weighted random)
# ---------------------------------------------------------------------------

def pick_numbers(
    scores: dict[int, float],
    n: int = 9,
    randomness: float = 0.18,
    seed: int | None = None,
) -> list[int]:
    """Επιλέγει N αριθμούς βάσει scores με μικρό τυχαίο θόρυβο."""
    rng = random.Random(seed)
    noisy = {num: max(sc + rng.uniform(0, randomness), 0.001) for num, sc in scores.items()}

    numbers = list(noisy.keys())
    weights = [noisy[num] for num in numbers]

    selected: list[int] = []
    rem_n = numbers[:]
    rem_w = weights[:]

    for _ in range(min(n, len(rem_n))):
        total = sum(rem_w)
        r = rng.uniform(0, total)
        cumul = 0.0
        for i, w in enumerate(rem_w):
            cumul += w
            if r <= cumul:
                selected.append(rem_n.pop(i))
                rem_w.pop(i)
                break

    return sorted(selected)


# ---------------------------------------------------------------------------
# Fallback: μαθηματική κατανομή (χωρίς δεδομένα)
# ---------------------------------------------------------------------------

def statistical_pick(n: int = 9, seed: int | None = None) -> list[int]:
    """Balanced sampling ανά δεκάδα όταν δεν υπάρχουν δεδομένα."""
    rng = random.Random(seed)
    decade_w = []
    for d in range(8):
        mid = d * 10 + 5.5
        decade_w.append(1.0 - 0.3 * abs(mid - 40.5) / 40.5)

    picks: set[int] = set()
    attempts = 0
    while len(picks) < n and attempts < 1000:
        attempts += 1
        total = sum(decade_w)
        r = rng.uniform(0, total)
        cumul, chosen = 0.0, 0
        for d, w in enumerate(decade_w):
            cumul += w
            if r <= cumul:
                chosen = d
                break
        picks.add(rng.randint(chosen * 10 + 1, chosen * 10 + 10))

    return sorted(list(picks)[:n])


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_stats_from_api(stats: dict[int, dict]) -> None:
    """Εκτυπώνει στατιστικά από OPAP API."""
    hot   = sorted(stats.items(), key=lambda x: -x[1]["occurrences"])[:10]
    cold  = sorted(stats.items(), key=lambda x:  x[1]["occurrences"])[:10]
    overdue = sorted(stats.items(), key=lambda x: -x[1]["lastDraw"])[:10]

    print(f"\n{'='*54}")
    print(f"  ΣΤΑΤΙΣΤΙΚΑ KINO (OPAP API)")
    print(f"{'='*54}")
    print(f"  TOP 10 HOT     : {[n for n, _ in hot]}")
    print(f"  TOP 10 COLD    : {[n for n, _ in cold]}")
    print(f"  TOP 10 OVERDUE : {[n for n, _ in overdue]}")
    print(f"{'='*54}\n")


def print_stats_from_draws(draws: list[list[int]]) -> None:
    """Εκτυπώνει στατιστικά από raw draws."""
    freq  = frequency_map(draws)
    gaps  = gap_analysis(draws)
    exp   = len(draws) * DRAW_SIZE / TOTAL_NUMBERS

    hot     = sorted(freq.items(), key=lambda x: -x[1])[:10]
    cold    = sorted(freq.items(), key=lambda x:  x[1])[:10]
    overdue = sorted(gaps.items(), key=lambda x: -x[1])[:10]

    print(f"\n{'='*54}")
    print(f"  ΣΤΑΤΙΣΤΙΚΑ KINO ({len(draws)} raw κληρώσεις)")
    print(f"  Αναμενόμενη συχνότητα/αριθμό: {exp:.1f}")
    print(f"{'='*54}")
    print(f"  TOP 10 HOT     : {[n for n, _ in hot]}")
    print(f"  TOP 10 COLD    : {[n for n, _ in cold]}")
    print(f"  TOP 10 OVERDUE : {[n for n, _ in overdue]}")
    print(f"{'='*54}\n")
