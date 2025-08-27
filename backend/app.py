import os
import json
import threading
from flask import Flask, jsonify, request, send_from_directory, render_template
from flask_cors import CORS

from valorantFetch import fetch_player_data, load_players

app = Flask(__name__, static_folder="../frontend", template_folder="../frontend")
CORS(app)

# ========= Progress State ==========
progress = {
    "logs": [],
    "current": 0,
    "total": 0,
    "running": False
}

def log(msg: str):
    """Log to memory + stdout"""
    progress["logs"].append(msg)
    print(msg, flush=True)

# ========= Background Scraper ==========
def run_scraper(players):
    progress["running"] = True
    progress["logs"] = []
    progress["current"] = 0
    progress["total"] = len(players)

    log(f"[INFO] Starting scrape for {len(players)} players...")

    results = []
    for idx, (name, tag) in enumerate(players.items(), 1):
        try:
            log(f"[INFO] Fetching {name}#{tag}...")
            player_data = fetch_player_data({name: tag})[0]
            results.append(player_data)
            log(f"[OK] Finished {name}#{tag}")
        except Exception as e:
            log(f"[ERROR] {name}#{tag}: {e}")
        progress["current"] = idx

    # Save last results
    with open("weeklyStats.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    log("[INFO] Scraper finished.")
    progress["running"] = False

# ========= API Routes ==========

@app.route("/")
def home():
    # serve frontend home.html
    return send_from_directory(app.static_folder, "home.html")

@app.route("/players", methods=["GET"])
def get_players():
    return jsonify(load_players())

@app.route("/add-player", methods=["POST"])
def add_player():
    data = request.json
    name, tag = data.get("name"), data.get("tag")
    players = load_players()
    players[name] = tag
    with open("players.json", "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)
    log(f"[INFO] Added player {name}#{tag}")
    return jsonify(players)

@app.route("/remove-player", methods=["POST"])
def remove_player():
    data = request.json
    name = data.get("name")
    players = load_players()
    if name in players:
        del players[name]
        with open("players.json", "w", encoding="utf-8") as f:
            json.dump(players, f, indent=2, ensure_ascii=False)
        log(f"[INFO] Removed player {name}")
    return jsonify(players)

@app.route("/run-scraper", methods=["POST"])
def run_scraper_endpoint():
    players = load_players()
    if not players:
        return jsonify({"error": "No players to scrape"}), 400

    if progress["running"]:
        return jsonify({"error": "Scraper already running"}), 400

    thread = threading.Thread(target=run_scraper, args=(players,))
    thread.start()
    return jsonify({"status": "started", "total": len(players)})

@app.route("/status", methods=["GET"])
def status():
    return jsonify(progress)

# ========= Static Files ==========
@app.route('/<path:path>')
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

@app.route("/save-player", methods=["POST"])
def save_player_alias():
    # Reuse the existing /add-player logic
    return add_player()

@app.route("/scraper-status", methods=["GET"])
def scraper_status_alias():
    # Shape it as { status, logs, progress } to match the frontend
    state = (
        "running" if progress.get("running") else
        ("done" if progress.get("total", 0) > 0 and progress.get("current", 0) >= progress.get("total", 0) else "idle")
    )
    return jsonify({
        "status": state,
        "logs": progress.get("logs", []),
        "progress": {
            "current": progress.get("current", 0),
            "total": progress.get("total", 0)
        }
    })

# ========= Entrypoint ==========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
