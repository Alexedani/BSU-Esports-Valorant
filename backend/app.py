from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import threading
import os

from valorantScrape import fetch_player_data 

app = Flask(__name__)
CORS(app)

PLAYERS_FILE = "players.json"
SCRAPE_STATUS_FILE = "scrape_status.json"

# ---------------- Players helpers ----------------
def load_players():
    if not os.path.exists(PLAYERS_FILE):
        return {}
    try:
        with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}

def save_players(players):
    with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)

# ---------------- Scraper helpers ----------------
def save_status(status, results=None):
    data = {"status": status}
    if results is not None:
        data["results"] = results
    with open(SCRAPE_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_status():
    if not os.path.exists(SCRAPE_STATUS_FILE):
        return {"status": "idle"}
    with open(SCRAPE_STATUS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def run_scraper_thread(players):
    try:
        save_status("running")
        results = fetch_player_data(players)
        save_status("done", results)
    except Exception as e:
        save_status("error", {"message": str(e)})

# ---------------- API routes ----------------
@app.route("/players", methods=["GET"])
def get_players():
    return jsonify(load_players())

@app.route("/players", methods=["POST"])
def add_player():
    data = request.json
    name, tag = data.get("name"), data.get("tag")
    if not name or not tag:
        return jsonify({"error": "Name and tag required"}), 400
    players = load_players()
    players[name] = tag
    save_players(players)
    return jsonify(players)

@app.route("/players/<name>", methods=["DELETE"])
def delete_player(name):
    players = load_players()
    if name in players:
        del players[name]
        save_players(players)
    return jsonify(players)

@app.route("/run-scraper", methods=["POST"])
def run_scraper():
    players = load_players()
    if not players:
        return jsonify({"error": "No players configured"}), 400

    # start background thread
    thread = threading.Thread(target=run_scraper_thread, args=(players,))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "scraper started", "players": players})

@app.route("/scraper-status", methods=["GET"])
def scraper_status():
    return jsonify(load_status())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
