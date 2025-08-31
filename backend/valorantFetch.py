import os
import json
import time
import requests
from urllib.parse import quote
from datetime import datetime, timedelta, timezone
from dateutil import parser as dateparser
import threading

# ========= Local storage paths =========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "players.json")
WEEKLY_STATS_PATH = os.path.join(BASE_DIR, "weeklyStats.json")

# Google Apps Script Web App (POST endpoint)
WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzhP5SFu0ewcDedjIjcpyelc4lzELJWqupbPQH0kXCaRUpt36ITjtFPB1YaIbJKgmEJqQ/exec"

# HenrikDev
BASEURL_RANK    = "https://api.henrikdev.xyz/valorant/v2/mmr"
BASEURL_MATCHES = "https://api.henrikdev.xyz/valorant/v4/matches"
REGION   = "na"
PLATFORM = "pc"
API_KEY  = "HDEV-1c01af3c-49eb-44a1-a55e-b1ecf252ad12"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

# ========= Helpers =========
def load_players():
    """Read players.json -> dict like {'name': 'tag', ...}"""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print("[ERROR] load_players:", e, flush=True)
        return {}

def _sleep_for_rate_limit(resp):
    ra = resp.headers.get("Retry-After")
    if ra:
        try:
            return max(1, int(float(ra)))
        except Exception:
            pass
    xr = resp.headers.get("x-ratelimit-reset")
    if xr:
        try:
            return max(1, int(float(xr)))
        except Exception:
            pass
    return 60

def _num(x, default=0.0):
    """Coerce number (handles int/float/str/dict)."""
    try:
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, str):
            return float(x.strip().replace(",", ""))
        if isinstance(x, dict):
            for k in ("dealt", "made", "damage", "total", "overall", "value", "won", "lost"):
                if k in x:
                    return _num(x[k], default)
        return default
    except Exception:
        return default


# ========= Watchdog =========
class Watchdog:
    """Simple cross-platform watchdog using threading.Timer."""
    def __init__(self, timeout, name):
        self.timeout = timeout
        self.name = name
        self._timer = None
        self._expired = False

    def _timeout(self):
        self._expired = True
        print(f"[ERROR] Watchdog timeout fired for {self.name}", flush=True)

    def start(self):
        self._timer = threading.Timer(self.timeout, self._timeout)
        self._timer.start()

    def cancel(self):
        if self._timer:
            self._timer.cancel()

    def expired(self):
        return self._expired


# ========= Rank =========
def fetch_rank(name, tag):
    url = f"{BASEURL_RANK}/{REGION}/{name}/{tag}"
    headers = {"Authorization": API_KEY, "User-Agent": UA}
    print(f"[INFO] Fetching rank for {name}#{tag} -> {url}", flush=True)

    resp = requests.get(url, headers=headers, timeout=15)

    if resp.status_code == 404:
        msg = f"Player {name}#{tag} not found or profile hidden"
        print(f"[ERROR] {msg}", flush=True)
        raise Exception(msg)

    if resp.status_code == 429:
        secs = _sleep_for_rate_limit(resp)
        print(f"[WARN] 429 on rank. Sleeping {secs}s…", flush=True)
        time.sleep(secs)
        resp = requests.get(url, headers=headers, timeout=15)

    resp.raise_for_status()
    body = resp.json().get("data", {})
    cur = body.get("current_data", {}) or body.get("current", {})

    tier = cur.get("currenttierpatched") or cur.get("current_tier_patched") or "Unranked"
    imgs = cur.get("images", {}) or body.get("images", {})
    rank_img = imgs.get("large") or imgs.get("largeicon")
    rr = cur.get("ranking_in_tier")

    rank_data = {"currenttier": tier, "rankImage": rank_img, "rr": rr}
    print(f"[OK] Rank fetched: {rank_data}", flush=True)
    return rank_data


# ========= Matches =========
def fetch_agent_stats(name, tag, region=REGION, platform=PLATFORM):
    """Aggregate last 7 days of competitive matches by agent."""
    print(f"[INFO] Fetching match history for {name}#{tag}", flush=True)
    headers = {"Authorization": API_KEY, "User-Agent": UA}

    enc_name = quote(str(name), safe="")
    enc_tag  = quote(str(tag),  safe="")

    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)

    aggregated = {}
    start = 0
    size = 10
    page_count = 0
    max_pages = 15  # safety cap

    want_name = (name or "").strip().lower()
    want_tag  = (tag  or "").strip().lower()

    def same_player(p):
        n = (p.get("name") or "").strip().lower()
        t = (p.get("tag")  or "").strip().lower()
        return n == want_name and t == want_tag

    while True:
        page_count += 1
        if page_count > max_pages:
            print(f"[WARN] Max pages ({max_pages}) reached for {name}#{tag}, stopping early.", flush=True)
            break

        url = f"{BASEURL_MATCHES}/{region}/{platform}/{enc_name}/{enc_tag}?mode=competitive&size={size}&start={start}"
        print(f"[DEBUG] Fetching {url}", flush=True)
        resp = requests.get(url, headers=headers, timeout=15)

        if resp.status_code == 429:
            secs = _sleep_for_rate_limit(resp)
            print(f"[WARN] 429 Too Many Requests — sleeping {secs} seconds", flush=True)
            time.sleep(secs)
            continue
        if resp.status_code == 404:
            msg = f"Player {name}#{tag} not found or profile hidden"
            print(f"[ERROR] {msg}", flush=True)
            raise Exception(msg)

        resp.raise_for_status()
        matches = resp.json().get("data", [])
        if not isinstance(matches, list) or not matches:
            print("[INFO] No more matches returned.", flush=True)
            break

        stop_early = False
        for match in matches:
            if not isinstance(match, dict):
                continue

            meta = match.get("metadata", {})
            started_at = meta.get("started_at")
            try:
                game_date = dateparser.parse(started_at).astimezone(timezone.utc) if started_at else now
            except Exception:
                game_date = now

            if game_date < cutoff:
                print(f"[INFO] Reached match older than 7 days ({game_date}), stopping.", flush=True)
                stop_early = True
                break

            players_list = match.get("players", []) or []
            player_obj = next((p for p in players_list if isinstance(p, dict) and same_player(p)), None)
            if not player_obj:
                continue

            agent_name = (player_obj.get("agent") or {}).get("name") or "Unknown"

            rounds_list = match.get("rounds", [])
            if isinstance(rounds_list, list) and rounds_list:
                total_rounds = len(rounds_list)
            else:
                total_rounds = int(_num(meta.get("rounds_played", 0))) or 1

            stats = player_obj.get("stats", {}) or {}
            damage_total = _num((stats.get("damage") or {}).get("dealt", 0))
            kills  = _num(stats.get("kills", 0))
            deaths = _num(stats.get("deaths", 0))
            kd = kills / (deaths if deaths else 1.0)
            adr = damage_total / float(total_rounds)

            win = False
            my_team_id = player_obj.get("team_id")
            teams_block = match.get("teams", [])
            if isinstance(teams_block, list):
                for tm in teams_block:
                    if tm.get("team_id") == my_team_id:
                        win = bool(tm.get("won"))
                        break

            agg = aggregated.setdefault(agent_name, {"games": 0, "totalADR": 0.0, "totalKD": 0.0, "wins": 0})
            agg["games"] += 1
            agg["totalADR"] += adr
            agg["totalKD"] += kd
            if win:
                agg["wins"] += 1

        if stop_early or len(matches) < size:
            break

        start += size
        time.sleep(1.5)

    for agent, st in list(aggregated.items()):
        g = max(1, st["games"])
        st["avgADR"]  = st["totalADR"] / g
        st["avgKD"]   = st["totalKD"] / g
        st["winRate"] = (st["wins"] / g) * 100.0
        del st["totalADR"], st["totalKD"], st["wins"]

    print(f"[OK] Aggregated stats for {name}#{tag}: {aggregated}", flush=True)
    return aggregated


# ========= Google Apps Script POST =========
def send_to_google_apps_script(weekly_stats: list, url: str = WEBAPP_URL, timeout: int = 20) -> bool:
    try:
        resp = requests.post(url, json=weekly_stats, headers={"Content-Type": "application/json"}, timeout=timeout)
        if resp.status_code != 200:
            print("[ERROR] GAS non-200:", resp.status_code, resp.text, flush=True)
            return False
        return True
    except requests.RequestException as e:
        print("[ERROR] RequestException:", str(e), flush=True)
        return False


# ========= Orchestrator =========
def fetch_player_data(players: dict, post=True):
    results = []

    for name, tag in players.items():
        entry = {"player": f"{name}#{tag}"}
        watchdog = Watchdog(300, f"{name}#{tag}")  # 5 minutes
        try:
            print(f"[DEBUG] Starting scrape for {name}#{tag}", flush=True)
            watchdog.start()

            rk = fetch_rank(name, tag)
            if watchdog.expired():
                raise TimeoutError(f"Timed out scraping {name}#{tag} (while fetching rank)")

            ag = fetch_agent_stats(name, tag)
            if watchdog.expired():
                raise TimeoutError(f"Timed out scraping {name}#{tag} (while fetching matches)")

            entry["rank"] = rk
            entry["agents"] = ag

        except TimeoutError as e:
            msg = str(e)
            print(f"[ERROR] {msg}", flush=True)
            entry["error"] = msg
            entry.setdefault("rank", None)
            entry.setdefault("agents", {})
        except Exception as e:
            msg = str(e) or "Unknown error"
            print(f"[ERROR] Failed for {name}#{tag}: {msg}", flush=True)
            entry["error"] = msg
            entry.setdefault("rank", None)
            entry.setdefault("agents", {})
        finally:
            watchdog.cancel()

        results.append(entry)

    try:
        with open(WEEKLY_STATS_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("[WARN] Could not write weeklyStats.json:", e, flush=True)

    if post:
        posted = send_to_google_apps_script(results)
        print("[INFO] Posted weekly stats to Google Sheets:", posted, flush=True)

    return results


# ========= Local run =========
if __name__ == "__main__":
    players = load_players()
    if not players:
        players = {
            "master": "bsu",
            "skelesis": "Folk"
        }
    fetch_player_data(players)
