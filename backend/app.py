from flask import Flask, jsonify, request
import json, os
from valorantScrape import fetch_player_data

app = Flask(__name__)
CONFIG_FILE = "players.json"


# helpers for reading/writing players.json
def load_players():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)  # dict of {name: tag}
    return {}

def save_players(players: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)


#API Routes

@app.route("/players", methods=["GET"])
def get_players():
    """Return all tracked players as {name: tag} dict"""
    return jsonify(load_players())


@app.route("/save-player", methods=["POST"])
def save_player():
    """
    Add or update a player in the config.
    Expected JSON: { "name": "愛青空", "tag": "skies" }
    """
    data = request.json
    if not data or "name" not in data or "tag" not in data:
        return jsonify({"error": "Missing name or tag"}), 400

    players = load_players()
    players[data["name"]] = data["tag"]  # add or overwrite
    save_players(players)
    return jsonify(players)


@app.route("/remove-player", methods=["POST"])
def remove_player():
    """
    Remove a player from the config.
    Expected JSON: { "name": "愛青空" }
    """
    data = request.json
    if not data or "name" not in data:
        return jsonify({"error": "Missing player name"}), 400

    players = load_players()
    if data["name"] in players:
        del players[data["name"]]
        save_players(players)
        return jsonify(players)
    else:
        return jsonify({"error": f"Player {data['name']} not found"}), 404


@app.route("/run-scraper", methods=["POST"])
def run_scraper_api():
    """
    Run the Valorant scraper with the current players.json
    and return the results.
    """
    data = fetch_player_data()
    return jsonify({"status": "success", "data": data})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
