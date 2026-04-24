"""
KINO Monitor — Flask backend
Polls OPAP every 5m15s, checks pattern rules, sends Telegram signals.
Runs 24/7 on Railway.
"""

import json
import os
import threading
import time
import uuid
from collections import deque
from datetime import datetime

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# ── Config file ──
CONFIG_FILE = "config.json"

DEFAULT_RULES = [
    {"id": "rule1",  "name": "ΚΑΝΟΝΑΣ 1 (Οριζόντιο)",  "trigger": [0,1,2,3],        "offsets": [0,1,2,3,10,11],   "duration": 4, "enabled": True},
    {"id": "rule2",  "name": "ΚΑΝΟΝΑΣ 2 (Τετράγωνο)",  "trigger": [0,1,10,11,20,21],"offsets": [0,1,10,11,20,21], "duration": 2, "enabled": True},
    {"id": "rule3",  "name": "ΚΑΝΟΝΑΣ 3 (Στήλη)",       "trigger": [0,10,20,30],      "offsets": [0,10,20,30,40,50],"duration": 2, "enabled": True},
    {"id": "rule4",  "name": "ΚΑΝΟΝΑΣ 4 (Σταυρόνημα)",  "trigger": [0,1,2,10,20],    "offsets": [0,1,2,10,11,12],  "duration": 2, "enabled": True},
    {"id": "rule5",  "name": "ΚΑΝΟΝΑΣ 5",  "trigger": [], "offsets": [], "duration": 0, "enabled": False},
    {"id": "rule6",  "name": "ΚΑΝΟΝΑΣ 6",  "trigger": [], "offsets": [], "duration": 0, "enabled": False},
    {"id": "rule7",  "name": "ΚΑΝΟΝΑΣ 7",  "trigger": [], "offsets": [], "duration": 0, "enabled": False},
    {"id": "rule8",  "name": "ΚΑΝΟΝΑΣ 8",  "trigger": [], "offsets": [], "duration": 0, "enabled": False},
    {"id": "rule9",  "name": "ΚΑΝΟΝΑΣ 9",  "trigger": [], "offsets": [], "duration": 0, "enabled": False},
    {"id": "rule10", "name": "ΚΑΝΟΝΑΣ 10", "trigger": [], "offsets": [], "duration": 0, "enabled": False},
]

DEFAULT_CONFIG = {
    "token":   "",
    "targets": [{"id": str(uuid.uuid4()), "chatId": "", "label": "Κύρια Ομάδα", "enabled": True}],
    "rules":   DEFAULT_RULES,
    "gameId":  "1100",
}

GAME_OPTIONS = [
    {"id": "1100", "name": "Kino"},
    {"id": "5103", "name": "Lotto"},
    {"id": "5104", "name": "Joker"},
    {"id": "2100", "name": "Super 3"},
    {"id": "5106", "name": "Extra 5"},
]

# ── In-memory state ──
signals = deque(maxlen=100)
logs    = deque(maxlen=200)
state   = {"running": False, "lastDrawNo": None, "lastDraw": None}
_lock   = threading.Lock()


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                cfg = json.load(f)
            for k, v in DEFAULT_CONFIG.items():
                cfg.setdefault(k, v)
            return cfg
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


config = load_config()


# ── Logging ──
def add_log(typ, message):
    entry = {"id": str(uuid.uuid4()), "timestamp": datetime.now().strftime("%H:%M:%S"), "type": typ, "message": message}
    with _lock:
        logs.append(entry)
    print(f"[{typ.upper()}] {message}")


# ── OPAP API ──
def fetch_last_result(game_id):
    url = f"https://api.opap.gr/draws/v3.0/{game_id}/last-result-and-active"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        draw = data.get("last") or {}
        if not draw:
            return None
        numbers = (
            (draw.get("winningNumbers") or {}).get("list")
            or draw.get("winningNumbers")
            or draw.get("results")
            or []
        )
        return {
            "drawNo":   draw.get("drawId") or draw.get("drawNo") or 0,
            "drawTime": draw.get("drawTime") or "",
            "numbers":  [int(n) for n in numbers],
        }
    except Exception as e:
        add_log("error", f"OPAP: {e}")
        return None


# ── Rule engine ──
def check_rules(rules, winning_numbers):
    win_set = set(winning_numbers)
    matches = []
    for rule in rules:
        if not rule.get("enabled") or not rule.get("trigger"):
            continue
        for root in range(1, 81):
            trigger_nums = [root + o for o in rule["trigger"] if 1 <= root + o <= 80]
            if len(trigger_nums) != len(rule["trigger"]):
                continue
            if all(n in win_set for n in trigger_nums):
                suggestion = sorted([root + o for o in rule["offsets"] if 1 <= root + o <= 80])
                matches.append({"ruleName": rule["name"], "root": root, "suggestion": suggestion, "duration": rule.get("duration", 1)})
    return matches


# ── Telegram ──
def send_telegram(token, chat_id, text):
    if not token or not chat_id:
        return False, "Missing token or chat ID"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        data = r.json()
        return (True, "") if data.get("ok") else (False, data.get("description", "Error"))
    except Exception as e:
        return False, str(e)


def send_to_all(token, targets, text):
    results = []
    for t in targets:
        if not t.get("enabled") or not t.get("chatId", "").strip():
            continue
        ok, err = send_telegram(token, t["chatId"].strip(), text)
        results.append({"label": t.get("label", t["chatId"]), "success": ok, "error": err})
    return results


# ── Tick ──
def tick():
    if not state["running"]:
        return
    add_log("info", "Ανάκτηση αποτελεσμάτων OPAP…")
    result = fetch_last_result(config["gameId"])
    if not result or not result["numbers"]:
        add_log("warning", "Δεν ελήφθησαν αποτελέσματα ή εκτός ωραρίου.")
        return
    with _lock:
        state["lastDraw"] = result
    draw_no = result["drawNo"]
    if state["lastDrawNo"] == draw_no:
        add_log("info", f"Κλήρωση #{draw_no} ήδη ελέγχθηκε.")
        return
    state["lastDrawNo"] = draw_no
    add_log("success", f"Κλήρωση #{draw_no} · [{', '.join(str(n) for n in result['numbers'])}]")
    matches = check_rules(config["rules"], result["numbers"])
    if not matches:
        add_log("info", "Κανένας κανόνας δεν ενεργοποιήθηκε.")
        return
    add_log("success", f"🎯 {len(matches)} κανόνας/ες ενεργοποιήθηκε!")
    for m in matches:
        sugg = ", ".join(str(n) for n in m["suggestion"])
        msg = (f"🚨 *{m['ruleName']}*\n🎯 Root: {m['root']}\n"
               f"🎰 Παίξε: [{sugg}]\n⏳ Διάρκεια: {m['duration']} κληρώσεις\n📌 Κλήρωση: #{draw_no}")
        sent_to = []
        if config["token"]:
            for tr in send_to_all(config["token"], config["targets"], msg):
                if tr["success"]:
                    add_log("success", f"✈️ Telegram → {tr['label']}")
                    sent_to.append(tr["label"])
                else:
                    add_log("error", f"Telegram αποτυχία → {tr['label']}: {tr['error']}")
        else:
            add_log("warning", "Δεν υπάρχει Telegram token.")
        with _lock:
            signals.append({"id": str(uuid.uuid4()), "timestamp": datetime.now().strftime("%H:%M:%S"),
                            "ruleName": m["ruleName"], "root": m["root"], "suggestion": m["suggestion"],
                            "duration": m["duration"], "drawNo": draw_no, "sentTo": sent_to})


# ── Background scheduler (every 5m15s) ──
def scheduler_loop():
    while True:
        try:
            tick()
        except Exception as e:
            add_log("error", f"Scheduler: {e}")
        time.sleep(315)


threading.Thread(target=scheduler_loop, daemon=True).start()


# ── Routes ──
@app.route("/")
def index():
    return render_template("index.html", game_options=GAME_OPTIONS)


@app.route("/api/status")
def api_status():
    with _lock:
        return jsonify({"running": state["running"], "lastDraw": state["lastDraw"]})


@app.route("/api/config", methods=["GET"])
def api_config_get():
    return jsonify(config)


@app.route("/api/config", methods=["POST"])
def api_config_post():
    data = request.get_json(force=True)
    for key in ("token", "targets", "rules", "gameId"):
        if key in data:
            config[key] = data[key]
    save_config(config)
    add_log("info", "Ρυθμίσεις αποθηκεύτηκαν.")
    return jsonify({"ok": True})


@app.route("/api/start",  methods=["POST"])
def api_start():
    state["running"] = True
    add_log("info", "▶️ Monitor ξεκίνησε.")
    return jsonify({"ok": True})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    state["running"] = False
    add_log("info", "⏹️ Monitor σταμάτησε.")
    return jsonify({"ok": True})


@app.route("/api/check", methods=["POST"])
def api_check():
    add_log("info", "🔍 Χειροκίνητος έλεγχος…")
    result = fetch_last_result(config["gameId"])
    if not result or not result["numbers"]:
        add_log("warning", "Δεν ελήφθησαν αποτελέσματα.")
        return jsonify({"ok": False})
    with _lock:
        state["lastDraw"] = result
    add_log("success", f"Κλήρωση #{result['drawNo']} · [{', '.join(str(n) for n in result['numbers'])}]")
    matches = check_rules(config["rules"], result["numbers"])
    add_log("info", f"{len(matches)} κανόνας/ες ταιριάζουν.")
    for m in matches:
        add_log("success", f"→ {m['ruleName']} root={m['root']} [{', '.join(str(n) for n in m['suggestion'])}]")
    return jsonify({"ok": True, "drawNo": result["drawNo"], "matches": len(matches)})


@app.route("/api/signals")
def api_signals():
    with _lock:
        return jsonify(list(reversed(list(signals))))


@app.route("/api/logs")
def api_logs():
    with _lock:
        return jsonify(list(reversed(list(logs))))


@app.route("/api/clear-signals", methods=["POST"])
def api_clear_signals():
    with _lock:
        signals.clear()
    return jsonify({"ok": True})


@app.route("/api/clear-logs", methods=["POST"])
def api_clear_logs():
    with _lock:
        logs.clear()
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    add_log("info", f"🚀 KINO Monitor starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
