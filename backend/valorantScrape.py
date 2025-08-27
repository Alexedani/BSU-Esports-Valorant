import urllib
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, StaleElementReferenceException
import time as _time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
import time
import requests
import json
from datetime import datetime, timedelta
import os

CONFIG_FILE = "players.json"

def load_players():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)  # dict of {name: tag}
    return {}

WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzhP5SFu0ewcDedjIjcpyelc4lzELJWqupbPQH0kXCaRUpt36ITjtFPB1YaIbJKgmEJqQ/exec"
BASEURL_RANK = "https://api.henrikdev.xyz/valorant/v2/mmr"
REGION = "na"
API_KEY = "HDEV-1c01af3c-49eb-44a1-a55e-b1ecf252ad12"

def fetch_rank(name, tag):
    url = f"{BASEURL_RANK}/{REGION}/{name}/{tag}"
    headers = {"Authorization": API_KEY}
    print(f"[INFO] Fetching rank for {name}#{tag} -> {url}")
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()["data"]

    rank_data = {
        "currenttier": data.get("current_data", {}).get("currenttierpatched", "Unranked"),
        "rankImage": data.get("current_data", {}).get("images", {}).get("large"),
        "rr": data.get("current_data", {}).get("ranking_in_tier")
    }
    print(f"[OK] Rank fetched: {rank_data}")
    return rank_data

# === NEW: driver helper ===
def make_driver():
    options = uc.ChromeOptions()

    if os.environ.get("RENDER", "false").lower() == "true":
        # Headless mode for Render
        options.headless = True
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--remote-debugging-port=9222")
    else:
        # Local development
        options.headless = False

    options.add_argument("user-agent=Mozilla/5.0")
    return uc.Chrome(options=options, use_subprocess=True)


#Helper for fetchAgentStats
def get_stat_value(row, label_text):
    for block in row.select(".trn-match-row__block"):
        label = block.select_one(".trn-match-row__text-label")
        value = block.select_one(".trn-match-row__text-value")
        if label and value and label_text.lower() in label.get_text(strip=True).lower():
            try:
                return float(value.get_text(strip=True))
            except:
                return None
    return None

def _rows_count(driver):
    return len(driver.find_elements(By.CSS_SELECTOR, ".trn-match-row"))

def _wait_button_ready_or_stale(driver, btn, timeout=8):
    end = _time.time() + timeout
    while _time.time() < end:
        try:
            _ = btn.is_enabled()
            classes = (btn.get_attribute("class") or "")
            if "loading" not in classes.lower():
                return True
        except StaleElementReferenceException:
            return True
        _time.sleep(0.15)
    return False

def _wait_for_progress(driver, before_rows, max_wait=15.0, idle_grace=1.5):
    start = _time.time()
    last_change = start
    last_count = _rows_count(driver)
    while True:
        now = _time.time()
        cur = _rows_count(driver)
        if cur > before_rows:
            return True, cur
        if cur != last_count:
            last_change = now
            last_count = cur
        if (now - start) >= max_wait:
            return False, cur
        if (now - last_change) >= idle_grace:
            return False, cur
        _time.sleep(0.2)

def fetch_agent_stats(name, tag):
    print(f"[INFO] Starting scraper for {name}#{tag}")
    driver = make_driver()   # <<< USE NEW DRIVER

    try:
        safe_name = urllib.parse.quote(name)
        safe_tag = urllib.parse.quote(tag)
        url = f"https://tracker.gg/valorant/profile/riot/{safe_name}%23{safe_tag}/matches?platform=pc&playlist=competitive"
        print(f"[INFO] Opening URL: {url}")

        driver.get(url)
        time.sleep(3)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".trn-match-row"))
        )
        print("[OK] Match rows detected")

        # ... rest of your scraping logic unchanged ...

        soup = BeautifulSoup(driver.page_source, "html.parser")
        aggregated = {}
        seen_match_ids = set()

        all_rows = soup.select("div.trn-match-row")
        print(f"[INFO] Total .trn-match-row elements found: {len(all_rows)}")

        # loop unchanged...
        # ...

        return aggregated

    finally:
        driver.quit()

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
        detail = getattr(e, "response", None)
        if detail is not None:
            try:
                print("[ERROR] RequestException:", detail.status_code, detail.json())
            except Exception:
                print("[ERROR] RequestException:", detail.status_code, detail.text)
        else:
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

if __name__ == "__main__":
    players = {  # test locally
        "master": "bsu"
    }
    fetch_player_data(players)
