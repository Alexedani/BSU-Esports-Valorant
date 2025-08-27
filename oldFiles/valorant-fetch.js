const axios = require('axios');
const fs = require('fs');

const players = {
    愛青空: "skies",
    orphan: "K0s",
    Skelesis: "folk",
    master: "bsu",
    Prestige: "bsu"
}

const BASEURL_RANK = "https://api.henrikdev.xyz/valorant/v2/mmr";
const BASEURL_MATCHES = "https://api.henrikdev.xyz/valorant/v3/matches";
const REGION = "na"; 
const API_KEY = "HDEV-1c01af3c-49eb-44a1-a55e-b1ecf252ad12"; 
const WEBAPP_URL = "https://script.google.com/macros/s/AKfycbzaO1zn7lp2mc0u2Sr7g3bSITTCPXi6fb2kQXweeSN7kojyxGSiJ1CEt4L1Vr9hU4F2Bw/exec";

//data we need: Current rank
//Ingame profile picutre/banner 
//Current RR
//Agent stats for the last 7 days

function sevenDaysAgo() {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  //reset time to 12am so we dont miss any matches  
  d.setHours(0, 0, 0, 0);       
  return d;
}


async function fetchRank(name, tag) {
  const url = `${BASEURL_RANK}/${REGION}/${name}/${tag}`;
  const response = await axios.get(url, {
    headers: { Authorization: API_KEY }
  });
  const data = response.data.data;

  return {
    currenttier: data.current_data?.currenttierpatched || "Unranked",
    rankImage: data.current_data?.images?.large || null,
    rr: data.current_data?.ranking_in_tier ?? null
  };
}

async function fetchAgentStats(name, tag) {
  const cutoff = sevenDaysAgo();
  const agentStats = {};
  let page = 1;
  let keepFetching = true;

  while (keepFetching) {
    const url = `${BASEURL_MATCHES}/${REGION}/${name}/${tag}?filter=all&size=70&page=${page}`;
    const response = await axios.get(url, {
      headers: { Authorization: API_KEY }
    });

    const matches = response.data.data || [];
    if (matches.length === 0) break;

    for (const match of matches) {
      const gameDate = new Date(match.metadata.game_start * 1000);
      const mode = match.metadata.mode.toLowerCase();

      // ---- FILTER LOGIC ----
      // includes all competitive games from the last 7 days
      // includes all custom games played only on friday and saturday
      let include = false;

      if (mode === "competitive" && gameDate >= cutoff) {
        include = true; 
      } else if (mode === "custom") {
        const day = gameDate.getDay();
        if (day === 5 || day === 6) include = true; 
      }

      if (!include) continue;
      // ----------------------

      const player = match.players.all_players.find(
        p => p.name.toLowerCase() === name.toLowerCase() &&
             p.tag.toLowerCase() === tag.toLowerCase()
      );
      if (!player) continue;

      const agent = player.character;
      if (!agentStats[agent]) {
        agentStats[agent] = { games: 0, totalACS: 0, totalKD: 0, wins: 0 };
      }

      agentStats[agent].games += 1;

      // ACS = score / rounds
      const acs = player.stats.score / match.metadata.rounds_played;
      agentStats[agent].totalACS += acs;

      // KD = kills / deaths
      const kills = player.stats.kills;
      const deaths = player.stats.deaths;
      const kd = deaths > 0 ? kills / deaths : kills;
      agentStats[agent].totalKD += kd;

      // Wins
      const team = player.team.toLowerCase();
      if (match.teams[team]?.has_won) {
        agentStats[agent].wins += 1;
      }
    }

    if (matches.length < 70) keepFetching = false;
    else page++;
  }

  // Finalize averages
  for (const agent in agentStats) {
    const stats = agentStats[agent];
    stats.avgACS = stats.totalACS / stats.games;
    stats.avgKD = stats.totalKD / stats.games;
    stats.winRate = (stats.wins / stats.games) * 100;

    delete stats.totalACS;
    delete stats.totalKD;
    delete stats.wins;
  }

  return agentStats;
}

async function sendToGoogleAppsScript(data) {
  try {
    const resp = await axios.post(WEBAPP_URL, data, {
      headers: { 'Content-Type': 'application/json' }
    });
    //for testing
    //console.log('response:', resp.data);
    if (resp.data.status === 'error') {
      console.error('Server‑side error message:', resp.data.message);
    }
  } catch (err) {
    // test
    console.error('fail', 
      err.response?.data || err.message);
  }
}


async function fetchPlayerData() {
  const results = [];

  for (const name in players) {
    const tag = players[name];

    try {
      const rank = await fetchRank(name, tag);
      const agents = await fetchAgentStats(name, tag);

      results.push({
        player: `${name}#${tag}`,
        rank,
        agents
      });

      //Sends JSON to google apps script to be formatted
      sendToGoogleAppsScript(results);

    } catch (err) {
      console.error(`Error fetching ${name}#${tag}`, err.response?.data || err.message);
    }
  }

  fs.writeFileSync("weeklyStats.json", JSON.stringify(results, null, 2));
}


//fetchPlayerData();
// const data = JSON.parse(fs.readFileSync("./weeklyStats.json", "utf8"));
// sendToGoogleAppsScript(data);


