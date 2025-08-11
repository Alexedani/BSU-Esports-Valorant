const axios = require('axios');
const cheerio = require('cheerio');
const fs = require('fs');

const players = {
    sk1: "skies",
    KOS: "3650",
    Skelesis: "Folk",
    Master: "BSU",
    Prestige: "BSU"
}

const BASEURL = "https://tracker.gg/valorant/profile/riot/{playername}%23{tag}" 

//data we need: Current rank
//Ingame profile picutre/banner 
//Current RR

async function fetchOverviewData() {
    try {

        for(const player in players){
            const playerURL = BASEURL.replace("{playername}", player).replace("{tag}", players[player]);
            console.log(playerURL);
            const response = await axios();

            const RR = $('.mmr').text().trim();
            const rankImage = $('div.absolute.left-0.top-0 img').attr('src');
            const bannerImage = $('.rating-entry__rank-icon img').attr('src');
        }

    } catch (error) {
        console.error('Error fetching team data:', error);
        return null;
    }
}

fetchOverviewData();
