import urllib
import time
import requests
import json
from datetime import datetime, timedelta

WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzhP5SFu0ewcDedjIjcpyelc4lzELJWqupbPQH0kXCaRUpt36ITjtFPB1YaIbJKgmEJqQ/exec"
BASEURL_RANK = "https://api.henrikdev.xyz/valorant/v2/mmr"
BASEURL_MATCHES = "https://api.henrikdev.xyz/valorant/v3/matches"
REGION = "na"
API_KEY = "HDEV-1c01af3c-49eb-44a1-a55e-b1ecf252ad12"

HEADERS = {"Authorization": API_KEY}

def fetch_rank(name, tag):
    url = f"{BASEURL_RANK}/{REGION}/{name}/{tag}"
    print(f"[INFO] Fetching rank for {name}#{tag} -> {url}")
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    data = response.json()["data"]

    rank_data = {
        "currenttier": data.get("current_data", {}).get("currenttierpatched", "Unranked"),
        "rankImage": data.get("current_data", {}).get("images", {}).get("large"),
        "rr": data.get("current_data", {}).get("ranking_in_tier")
    }
    print(f"[OK] Rank fetched: {rank_data}")
    return rank_data


def fetch_agent_stats_api(name, tag, days=7):
    """
    Use HenrikDev API to pull matches in the last N days (competitive only).
    Aggregates stats by agent (avgADR, avgKD, winRate).
    """
    cutoff = datetime.now() - timedelta(days=days)
    aggregated = {}
    page = 1
    page_size = 10

    while True:
        url = f"{BASEURL_MATCHES}/{REGION}/{name}/{tag}?mode=competitive&size={page_size}&page={page}"
        print(f"[INFO] Fetching matches page {page} for {name}#{tag}")
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print(f"[WARN] Match fetch failed: {resp.status_code} {resp.text}")
            break

        matches = resp.json().get("data", [])
        if not matches:
            break  # no more pages

        stop_paging = False
        for match in matches:
            ts = match["metadata"]["game_start"]
            game_date = datetime.fromtimestamp(ts)
            if game_date < cutoff:
                stop_paging = True
                break

            for p in match["players"]["all_players"]:
                if (p["name"].lower() == name.lower() and
                    p["tag"].lower() == tag.lower()):
                    agent = p["character"]
                    kills = p["stats"]["kills"]
                    deaths = p["stats"]["deaths"] or 1
                    rounds = p["stats"].get("rounds_played", match["metadata"]["rounds_played"]) or 1
                    adr = p.get("damage_made", 0) / rounds
                    kd = kills / deaths
                    win = match["teams"][p["team"].lower()]["has_won"]

                    if agent not in aggregated:
                        aggregated[agent] = {"games": 0, "totalADR": 0.0, "totalKD": 0.0, "wins": 0}

                    aggregated[agent]["games"] += 1
                    aggregated[agent]["totalADR"] += adr
                    aggregated[agent]["totalKD"] += kd
                    if win:
                        aggregated[agent]["wins"] += 1

        if stop_paging:
            break

        page += 1  # move to next batch

    # Finalize stats
    for agent, stats in aggregated.items():
        games = stats["games"] or 1
        stats["avgADR"] = stats["totalADR"] / games
        stats["avgKD"] = stats["totalKD"] / games
        stats["winRate"] = (stats["wins"] / games) * 100
        del stats["totalADR"], stats["totalKD"], stats["wins"]

    print(f"[OK] Aggregated API stats for {name}#{tag}: {aggregated}")
    return aggregated



def send_to_google_apps_script(weekly_stats: list, url: str = WEBAPP_URL, timeout: int = 20) -> bool:
    try:
        resp = requests.post(url, json=weekly_stats, headers={"Content-Type": "application/json"}, timeout=timeout)
        if resp.status_code != 200:
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
            agents = fetch_agent_stats_api(name, tag)

            player_data = {"player": f"{name}#{tag}", "rank": rank, "agents": agents}
            results.append(player_data)

        except Exception as e:
            print(f"[ERROR] Failed for {name}#{tag}: {str(e)}")

    with open("weeklyStats.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    posted = send_to_google_apps_script(results)
    print("[INFO] Posted weekly stats to Google Sheets:", posted)

    return results


if __name__ == "__main__":
    # test with one player
    test_players = {"master": "bsu"}
    fetch_player_data(test_players)
