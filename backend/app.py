import os
import json
import threading
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from valorantFetch import fetch_player_data, load_players as lf_load_players  # keep original too

app = Flask(__name__, static_folder="../frontend", template_folder="../frontend")
CORS(app)

# ----- Single source of truth for players.json -----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYERS_PATH = os.path.join(BASE_DIR, "players.json")

def read_players():
    try:
        with open(PLAYERS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print("[ERROR] read_players:", e, flush=True)
        return {}

def write_players(players: dict):
    with open(PLAYERS_PATH, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)

# ========= Progress State ==========
progress = {"logs": [], "current": 0, "total": 0, "running": False}

def log(msg: str):
    progress["logs"].append(msg)
    print(msg, flush=True)

# ========= Background Scraper ==========
def run_scraper(players):
    progress.update({"running": True, "logs": [], "current": 0, "total": len(players)})
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

    with open(os.path.join(BASE_DIR, "weeklyStats.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    log("[INFO] Scraper finished.")
    progress["running"] = False

# ========= API Routes ==========
@app.route("/")
def home():
    return send_from_directory(app.static_folder, "home.html")

@app.route("/players", methods=["GET"])
def get_players():
    # Prefer our absolute-path reader; if empty, fall back to library loader for compatibility
    players = read_players()
    if not players:
        players = lf_load_players()
    return jsonify(players)

@app.route("/add-player", methods=["POST"])
def add_player():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    tag  = (data.get("tag")  or "").strip()
    if not name or not tag:
        return jsonify({"error": "name and tag required"}), 400

    players = read_players()
    players[name] = tag
    try:
        write_players(players)
    except Exception as e:
        log(f"[ERROR] write players.json failed: {e}")
        return jsonify({"error": "failed to write players.json"}), 500

    log(f"[INFO] Added player {name}#{tag}")
    return jsonify(players)

@app.route("/remove-player", methods=["POST"])
def remove_player():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()

    players = read_players()
    if name in players:
        del players[name]
        try:
            write_players(players)
            log(f"[INFO] Removed player {name}")
        except Exception as e:
            log(f"[ERROR] write players.json failed: {e}")
            return jsonify({"error": "failed to write players.json"}), 500
    return jsonify(players)

@app.route("/run-scraper", methods=["POST"])
def run_scraper_endpoint():
    players = read_players()
    if not players:
        return jsonify({"error": "No players to scrape"}), 400
    if progress["running"]:
        return jsonify({"error": "Scraper already running"}), 400
    threading.Thread(target=run_scraper, args=(players,), daemon=True).start()
    return jsonify({"status": "started", "total": len(players)})

@app.route("/status", methods=["GET"])
def status():
    return jsonify(progress)

# ---- Aliases the frontend expects ----
@app.route("/save-player", methods=["POST"])
def save_player_alias():
    return add_player()

@app.route("/scraper-status", methods=["GET"])
def scraper_status_alias():
    state = (
        "running" if progress.get("running") else
        ("done" if progress.get("total", 0) > 0 and progress.get("current", 0) >= progress.get("total", 0) else "idle")
    )
    return jsonify({
        "status": state,
        "logs": progress.get("logs", []),
        "progress": {"current": progress.get("current", 0), "total": progress.get("total", 0)}
    })

# ========= Static Files (keep LAST) ==========
@app.route('/<path:path>', methods=["GET"])
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

# ========= Entrypoint ==========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
