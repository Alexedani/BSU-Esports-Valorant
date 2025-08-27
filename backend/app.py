from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import os

from valorantFetch import fetch_player_data  # ✅ updated import

app = Flask(__name__)
CORS(app)

CONFIG_FILE = "players.json"

def load_players():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_players(players):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)

@app.route("/players", methods=["GET"])
def get_players():
    return jsonify(load_players())

@app.route("/players", methods=["POST"])
def add_player():
    data = request.get_json()
    players = load_players()
    players[data["name"]] = data["tag"]
    save_players(players)
    return jsonify({"status": "success"})

@app.route("/run-scraper", methods=["POST"])
def run_scraper():
    players = load_players()
    results = fetch_player_data(players)   # ✅ calls new API-based script
    return jsonify(results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
