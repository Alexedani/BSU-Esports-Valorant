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

#TODO: Write docs about this file
#How they can understand this script
#Reccomending they research tracker.gg in developer mode to inspect the elements and see how i get them
#Look into henrick dev api which is accurate


players = {
    "愛青空": "skies"
}

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
    """
    After clicking, either the button gets replaced (stale) or loses its loading state.
    We'll wait for either condition so we don't spam-click during a loading overlay.
    """
    end = _time.time() + timeout
    while _time.time() < end:
        try:
            # if element went stale -> we're good to proceed
            _ = btn.is_enabled()  # access will raise if stale
            classes = (btn.get_attribute("class") or "")
            # tracker.gg often toggles a 'loading' class on the button
            if "loading" not in classes.lower():
                return True
        except StaleElementReferenceException:
            return True
        _time.sleep(0.15)
    # timed out; we'll still continue but mark as not-ready
    return False

def _wait_for_progress(driver, before_rows, max_wait=15.0, idle_grace=1.5):
    """
    Polls .trn-match-row count every 200ms. Success if it increases.
    Also returns early if the count stays unchanged for idle_grace seconds.
    """
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
            # no changes for a while -> likely stalled
            return False, cur
        _time.sleep(0.2)



def fetch_agent_stats(name, tag):
    print(f"[INFO] Starting scraper for {name}#{tag}")

    options = uc.ChromeOptions()
    options.headless = False
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0")

    driver = uc.Chrome(options=options)

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

        # Click "Load More" up to N times, but break early if we see an old header
        max_clicks, clicks = 5, 0
        cutoff = datetime.now() - timedelta(days=7)

        while clicks < max_clicks:
            # If the last visible header is older than cutoff, stop early
            try:
                headers_now = driver.find_elements(By.CSS_SELECTOR, ".trn-match-header")
                if headers_now:
                    last_hdr_txt = headers_now[-1].text.strip()
                    parts = last_hdr_txt.split()
                    if len(parts) >= 2:
                        try:
                            dt = datetime.strptime(" ".join(parts[:2]) + f" {datetime.now().year}", "%b %d %Y")
                            if dt < cutoff:
                                print(f"[INFO] Last header {dt.date()} < cutoff; stop loading more.")
                                break
                        except:
                            pass
            except:
                pass

            # Robust "Load More" click with progress + stall handling
            try:
                xpath = "//button[span[normalize-space()='Load More']]"
                before_rows = _rows_count(driver)

                # Ensure the button is in view
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                _time.sleep(0.6)

                # Locate button
                btn = WebDriverWait(driver, 6).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )

                # Try native click; fall back to JS click
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", btn)
                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                    btn.click()
                except (ElementClickInterceptedException, StaleElementReferenceException, TimeoutException):
                    # fallback: refetch and JS click
                    btn = driver.find_element(By.XPATH, xpath)
                    driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", btn)
                    driver.execute_script("arguments[0].click();", btn)

                # Wait for the button to finish its loading state or become stale
                _wait_button_ready_or_stale(driver, btn, timeout=8)

                # Wait for progress (more rows) with idle watchdog
                progressed, after_rows = _wait_for_progress(driver, before_rows, max_wait=15.0, idle_grace=1.5)

                # If no progress, retry once gently
                if not progressed:
                    print("[WARN] No new rows after first click; retrying once...")
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    _time.sleep(0.6)
                    try:
                        # try to click again (fresh handle)
                        btn2 = driver.find_element(By.XPATH, xpath)
                        driver.execute_script("arguments[0].click();", btn2)
                        _wait_button_ready_or_stale(driver, btn2, timeout=8)
                        progressed, after_rows = _wait_for_progress(driver, before_rows, max_wait=12.0, idle_grace=1.2)
                    except Exception:
                        progressed = False
                        after_rows = _rows_count(driver)

                if not progressed:
                    # Bail out gracefully so the script never freezes here
                    print(f"[INFO] Clicked but no progress (rows stayed {before_rows}); stopping Load More.")
                    break

                clicks += 1
                print(f"[INFO] Clicked 'Load More' ({clicks}); rows {before_rows} -> {after_rows}")

            except TimeoutException:
                print("[INFO] No more 'Load More' button found — reached end of matches")
                break

        soup = BeautifulSoup(driver.page_source, "html.parser")
        aggregated = {}

        # Track unique matches to avoid double-counting
        seen_match_ids = set()

        # Iterate all rows once; bind each to its nearest previous header date
        all_rows = soup.select("div.trn-match-row")
        print(f"[INFO] Total .trn-match-row elements found: {len(all_rows)}")

        for idx, row in enumerate(all_rows):
            # Find match id (stable href to the match detail, if present)
            link = row.select_one("a[href*='/match/']")
            match_id = None
            if link and link.get("href"):
                # Use the tail (e.g., /valorant/match/abc123 -> abc123)
                match_id = link.get("href").rstrip("/").split("/")[-1].strip()

            # Fallback: hash a subset of stable text if no link (rare)
            if not match_id:
                match_id = f"hash:{hash(row.get_text(' ', strip=True)[:300])}"

            if match_id in seen_match_ids:
                # Skip duplicates
                continue
            seen_match_ids.add(match_id)

            # Attach to closest previous header
            header = row.find_previous("div", class_="trn-match-header")
            if not header:
                # If no header found, skip (cannot date-filter)
                continue

            header_text = header.get_text(" ", strip=True)
            parts = header_text.split()
            if len(parts) < 2:
                continue

            try:
                game_date = datetime.strptime(" ".join(parts[:2]) + f" {datetime.now().year}", "%b %d %Y")
            except:
                continue

            if game_date < cutoff:
                # Outside 7-day window
                continue

            # --- Extract stats per row ---
            # Agent
            agent_el = row.select_one(".vmr-agent img")
            if not agent_el:
                # sometimes agent may be in a different spot; skip if truly missing
                continue
            agent_name = agent_el.get("alt", "").strip() or "Unknown"

            # Win/Loss via row class
            classes = row.get("class") or []
            win = any(cls.endswith("--outcome-win") for cls in classes)

            # KD and ADR: support both "ADR" and "Avg Damage/Round" labels
            kd_val = get_stat_value(row, "K/D")
            adr_val = get_stat_value(row, "ADR")
            if adr_val is None:
                adr_val = get_stat_value(row, "Avg Damage/Round")

            # Aggregate
            if agent_name not in aggregated:
                aggregated[agent_name] = {"games": 0, "totalADR": 0.0, "totalKD": 0.0, "wins": 0}

            aggregated[agent_name]["games"] += 1
            if adr_val is not None:
                aggregated[agent_name]["totalADR"] += adr_val
            if kd_val is not None:
                aggregated[agent_name]["totalKD"] += kd_val
            if win:
                aggregated[agent_name]["wins"] += 1

        # Finalize averages
        for agent, stats in aggregated.items():
            games = stats["games"] or 1
            stats["avgADR"] = stats["totalADR"] / games
            stats["avgKD"] = stats["totalKD"] / games
            stats["winRate"] = (stats["wins"] / games) * 100
            del stats["totalADR"], stats["totalKD"], stats["wins"]

        print(f"\n[OK] Aggregated stats for {name}#{tag}: {aggregated}")
        return aggregated

    finally:
        driver.quit()

def send_to_google_apps_script(weekly_stats: list, url: str = WEBAPP_URL, timeout: int = 20) -> bool:
    """
    POST the weekly stats JSON (list) directly to a Google Apps Script Web App.
    Sends ONLY the raw weekly stats array—no wrapper keys.
    Returns True on HTTP 200; prints errors otherwise.
    """
    try:
        resp = requests.post(url, json=weekly_stats, headers={"Content-Type": "application/json"}, timeout=timeout)
        if resp.status_code != 200:
            # Try to surface server response for debugging
            try:
                print("[ERROR] GAS non-200:", resp.status_code, resp.json())
            except Exception:
                print("[ERROR] GAS non-200:", resp.status_code, resp.text)
            return False
        return True
    except requests.RequestException as e:
        # Network/timeout/TLS issues
        detail = getattr(e, "response", None)
        if detail is not None:
            try:
                print("[ERROR] RequestException:", detail.status_code, detail.json())
            except Exception:
                print("[ERROR] RequestException:", detail.status_code, detail.text)
        else:
            print("[ERROR] RequestException:", str(e))
        return False

def fetch_player_data():
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

    return results  # <-- added return so Flask can send results back


if __name__ == "__main__":
    print("[INFO] Running scraper directly...")
    fetch_player_data()
