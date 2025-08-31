import os
import json
import threading
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Only import the fetcher (load/save handled here via disk)
from valorantFetch import fetch_player_data

app = Flask(__name__, static_folder="../frontend", template_folder="../frontend")
CORS(app)

# ========= Local file storage =========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLAYERS_PATH = os.path.join(BASE_DIR, "players.json")
WEEKLY_STATS_PATH = os.path.join(BASE_DIR, "weeklyStats.json")

players_lock = threading.Lock()

def read_players() -> dict:
    with players_lock:
        try:
            with open(PLAYERS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            print("[ERROR] read_players:", e, flush=True)
            return {}

def write_players(players: dict):
    with players_lock:
        with open(PLAYERS_PATH, "w", encoding="utf-8") as f:
            json.dump(players, f, indent=2, ensure_ascii=False)

# ========= Progress State =========
progress = {"logs": [], "current": 0, "total": 0, "running": False}

def log(msg: str):
    progress["logs"].append(msg)
    print(msg, flush=True)

# ========= Background Scraper =========
def run_scraper(players: dict):
    progress["running"] = True
    progress["logs"] = []
    progress["current"] = 0
    progress["total"] = len(players)
    progress["status"] = "running"
    log(f"[INFO] Starting scrape for {len(players)} players...")

    results = []
    error_occurred = False

    for idx, (name, tag) in enumerate(players.items(), 1):
        try:
            log(f"[INFO] Fetching {name}#{tag}...")
            piece = fetch_player_data({name: tag}, post=False)[0]

            if "error" in piece:
                log(f"[ERROR] {name}#{tag}: {piece['error']}")
                results.append(piece)
                error_occurred = True
                break  # stop scraping immediately
            else:
                log(f"[OK] Finished {name}#{tag}")
                results.append(piece)

        except Exception as e:
            msg = str(e) or "Unknown error"
            log(f"[ERROR] {name}#{tag}: {msg}")
            results.append({"player": f"{name}#{tag}", "error": msg})
            error_occurred = True
            break  # stop scraping immediately

        finally:
            progress["current"] = idx

    if error_occurred:
        log("[ERROR] Scraper aborted due to errors.")
        progress["running"] = False
        progress["status"] = "aborted"
        return  # don’t post, don’t save

    # Post ONCE to Google Apps Script with full batch
    try:
        from valorantFetch import send_to_google_apps_script
        posted = send_to_google_apps_script(results)
        log(f"[INFO] Posted weekly stats to Google Sheets: {posted}")
    except Exception as e:
        log(f"[ERROR] Post to Google Sheets failed: {e}")

    # Save last results locally
    try:
        with open(WEEKLY_STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log(f"[WARN] Could not write weeklyStats.json: {e}")

    log("[INFO] Scraper finished successfully.")
    progress["running"] = False
    progress["status"] = "done"



# ========= API Routes =========
@app.route("/")
def home():
    return send_from_directory(app.static_folder, "home.html")

@app.route("/players", methods=["GET"])
def get_players():
    return jsonify(read_players())

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
    if not name:
        return jsonify({"error": "name required"}), 400

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

# ---- Aliases ----
@app.route("/save-player", methods=["POST"])
def save_player_alias():
    return add_player()

@app.route("/scraper-status", methods=["GET"])
def scraper_status_alias():
    # Always prefer explicit status set in run_scraper
    state = progress.get("status", "idle")
    return jsonify({
        "status": state,
        "logs": progress.get("logs", []),
        "progress": {
            "current": progress.get("current", 0),
            "total": progress.get("total", 0)
        }
    })


# ========= Static Files =========
@app.route("/<path:path>", methods=["GET"])
def static_proxy(path):
    return send_from_directory(app.static_folder, path)

# ========= Entrypoint =========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
