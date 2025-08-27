import requests
import json
import time
from datetime import datetime, timedelta
from dateutil import parser as dateparser
import os

# --- Config ---
CONFIG_FILE = "players.json"
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzhP5SFu0ewcDedjIjcpyelc4lzELJWqupbPQH0kXCaRUpt36ITjtFPB1YaIbJKgmEJqQ/exec"
BASEURL_RANK = "https://api.henrikdev.xyz/valorant/v2/mmr"
BASEURL_MATCHES = "https://api.henrikdev.xyz/valorant/v4/matches"
REGION = "na"
API_KEY = "HDEV-1c01af3c-49eb-44a1-a55e-b1ecf252ad12"

# --- Helpers ---
def load_players():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def fetch_rank(name, tag):
    url = f"{BASEURL_RANK}/{REGION}/{name}/{tag}"
    headers = {"Authorization": API_KEY}
    print(f"[INFO] Fetching rank for {name}#{tag} -> {url}")
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()["data"]

    rank_data = {
        "currenttier": data.get("current_data", {}).get("currenttierpatched", "Unranked"),
        "rankImage": data.get("current_data", {}).get("images", {}).get("large"),
        "rr": data.get("current_data", {}).get("ranking_in_tier")
    }
    print(f"[OK] Rank fetched: {rank_data}")
    return rank_data

def fetch_agent_stats(name, tag):
    print(f"[INFO] Fetching match history for {name}#{tag}")
    headers = {"Authorization": API_KEY}
    now = datetime.now(datetime.utcnow().astimezone().tzinfo)
    cutoff = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)

    aggregated = {}
    start = 0
    size = 10
    done = False

    while not done:
        url = f"{BASEURL_MATCHES}/{REGION}/pc/{name}/{tag}?mode=competitive&size={size}&start={start}"
        print(f"[DEBUG] Fetching {url}")
        resp = requests.get(url, headers=headers)

        # --- Handle rate limits ---
        if resp.status_code == 429:
            reset_after = int(resp.headers.get("x-ratelimit-reset", 60))
            print(f"[WARN] 429 Too Many Requests — sleeping {reset_after} seconds")
            time.sleep(reset_after)
            continue

        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            print("[INFO] No more matches returned.")
            break

        for match in data:
            meta = match.get("metadata", {})
            game_date = dateparser.parse(meta.get("started_at"))

            if game_date < cutoff:
                print(f"[INFO] Reached match older than 7 days ({game_date}), stopping.")
                done = True
                break

            # Did this player participate?
            player_obj = None
            for p in match.get("players", []):
                if p.get("name") == name and p.get("tag") == tag:
                    player_obj = p
                    break

            if not player_obj:
                continue

            agent_name = player_obj.get("agent", {}).get("name", "Unknown")
            stats = player_obj.get("stats", {})
            adr = stats.get("damage", {}).get("dealt", 0) / max(1, match["metadata"].get("game_length_in_ms", 1) / (1000 * 120))  # rough ADR estimate
            kd = stats.get("kills", 0) / max(1, stats.get("deaths", 1))
            win = any(team.get("team_id") == player_obj.get("team_id") and team.get("won") for team in match.get("teams", []))

            if agent_name not in aggregated:
                aggregated[agent_name] = {"games": 0, "totalADR": 0.0, "totalKD": 0.0, "wins": 0}

            aggregated[agent_name]["games"] += 1
            aggregated[agent_name]["totalADR"] += adr
            aggregated[agent_name]["totalKD"] += kd
            if win:
                aggregated[agent_name]["wins"] += 1

        start += size
        time.sleep(2)  # pacing requests

    # Finalize averages
    for agent, stats in aggregated.items():
        games = stats["games"]
        stats["avgADR"] = stats["totalADR"] / games
        stats["avgKD"] = stats["totalKD"] / games
        stats["winRate"] = (stats["wins"] / games) * 100
        del stats["totalADR"], stats["totalKD"], stats["wins"]

    print(f"[OK] Aggregated stats for {name}#{tag}: {aggregated}")
    return aggregated

def send_to_google_apps_script(weekly_stats: list, url: str = WEBAPP_URL, timeout: int = 20) -> bool:
    try:
        resp = requests.post(url, json=weekly_stats, headers={"Content-Type": "application/json"}, timeout=timeout)
        if resp.status_code != 200:
            try:
                print("[ERROR] GAS non-200:", resp.status_code, resp.json())
            except Exception:
                print("[ERROR] GAS non-200:", resp.status_code, resp.text)
            return False
        return True
    except requests.RequestException as e:
        print("[ERROR] RequestException:", str(e))
        return False

def fetch_player_data(players: dict):
    results = []
    for name, tag in players.items():
        try:
            rank = fetch_rank(name, tag)
            agents = fetch_agent_stats(name, tag)
            player_data = {"player": f"{name}#{tag}", "rank": rank, "agents": agents}
            results.append(player_data)
        except Exception as e:
            print(f"[ERROR] Failed for {name}#{tag}: {str(e)}")

    with open("weeklyStats.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    posted = send_to_google_apps_script(results)
    print("[INFO] Posted weekly stats to Google Sheets:", posted)

    return results

# --- Run locally ---
if __name__ == "__main__":
    players = {
        "master": "bsu"
    }
    fetch_player_data(players)
