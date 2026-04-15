"""
Kino Allwyn.gr — Flask Web UI
"""

from flask import Flask, render_template, jsonify, request
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from fetch_data import load_statistics, load_draws
from analysis import (
    score_from_statistics,
    score_from_draws,
    pick_numbers,
    statistical_pick,
)

app = Flask(__name__)


def generate_prediction(count: int = 9, seed: int | None = None) -> dict:
    """Generates prediction and returns result dict."""
    numbers: list[int] = []
    method = ""
    draw_count = 0

    # Strategy 1: OPAP Statistics API
    stats = load_statistics(draw_range=1801)
    if stats and len(stats) >= 70:
        scores = score_from_statistics(stats)
        numbers = pick_numbers(scores, n=count, seed=seed)
        method = f"OPAP Statistics API (1801 κληρώσεις)"
        draw_count = 1801

        # Build top stats for display
        hot     = sorted(stats.items(), key=lambda x: -x[1]["occurrences"])[:10]
        cold    = sorted(stats.items(), key=lambda x:  x[1]["occurrences"])[:10]
        overdue = sorted(stats.items(), key=lambda x: -x[1]["lastDraw"])[:10]
        stats_data = {
            "hot":     [n for n, _ in hot],
            "cold":    [n for n, _ in cold],
            "overdue": [n for n, _ in overdue],
        }
    else:
        # Strategy 2: Raw draws
        draws = load_draws(limit=200)
        if len(draws) >= 10:
            scores = score_from_draws(draws)
            numbers = pick_numbers(scores, n=count, seed=seed)
            method = f"Ανάλυση raw draws ({len(draws)} κληρώσεις)"
            draw_count = len(draws)
            stats_data = {}
        else:
            # Fallback
            if seed is None:
                seed = int(datetime.now().timestamp())
            numbers = statistical_pick(n=count, seed=seed)
            method = "Μαθηματική κατανομή (χωρίς δεδομένα API)"
            stats_data = {}

    return {
        "numbers": numbers,
        "method": method,
        "draw_count": draw_count,
        "count": count,
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "stats": stats_data,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/predict")
def api_predict():
    count = request.args.get("count", 9, type=int)
    seed  = request.args.get("seed",  None, type=int)
    count = max(1, min(20, count))
    result = generate_prediction(count=count, seed=seed)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
