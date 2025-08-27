from flask import Flask, jsonify, request
from flask_cors import CORS
import os, json
from valorantScrape import fetch_player_data  # <-- make sure file is named valorantScrape.py (lowercase)
 
app = Flask(__name__)
CORS(app)

CONFIG_FILE = "players.json"


# -----------------------------
# Helpers
# -----------------------------
def load_players():
    """Load players from JSON file safely."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if not data:
                    return {}  # empty file
                return json.loads(data)  # parse JSON
        except json.JSONDecodeError:
            return {}  # corrupted file → reset
    return {}


def save_players(players: dict):
    """Save players to JSON file."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)


# -----------------------------
# Routes
# -----------------------------
@app.route("/players", methods=["GET"])
def get_players():
    return jsonify(load_players())


@app.route("/save-player", methods=["POST"])
def save_player():
    data = request.get_json(force=True)
    name = data.get("name")
    tag = data.get("tag")

    if not name or not tag:
        return jsonify({"error": "Missing name or tag"}), 400

    players = load_players()
    players[name] = tag  # overwrite or add
    save_players(players)

    return jsonify(players)


@app.route("/remove-player", methods=["POST"])
def remove_player():
    data = request.get_json(force=True)
    name = data.get("name")

    if not name:
        return jsonify({"error": "Missing name"}), 400

    players = load_players()
    if name in players:
        del players[name]
        save_players(players)

    return jsonify(players)


@app.route("/run-scraper", methods=["POST"])
def run_scraper():
    players = load_players()
    if not players:
        return jsonify({"error": "No players to scrape"}), 400

    results = fetch_player_data(players)
    return jsonify(results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
