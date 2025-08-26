from flask import Flask, jsonify
from valorantScrape import fetch_player_data  # import your function

app = Flask(__name__)

@app.route("/run-scraper", methods=["POST"])
def run_scraper_api():
    try:
        data = fetch_player_data()
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
