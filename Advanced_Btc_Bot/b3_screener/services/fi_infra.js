const axios = require('axios');
const cheerio = require('cheerio');
const { getFiiMetadata } = require('./investidor10');
const { KNOWN_INFRAS } = require('./config/fii_lists');

/**
 * FI-Infra Service
 * Dynamically scrapes tickers from Investidor10 and fetches their metadata
 */

async function getFIInfra(selicParam = null) {
    const SEGMENT_URL = 'https://investidor10.com.br/fiis/segmento/fi-infra/';
    const headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    };

    console.log('📡 Discovering FI-Infra tickers from Investidor10...');
    let tickers = [];
    try {
        const response = await axios.get(SEGMENT_URL, { headers, timeout: 10000 });
        const $ = cheerio.load(response.data);

        // Find tickers in the rankings table (ID: rankigns - with typo as used by the site)
        // We find the table, then look for links within it that match the ticker pattern
        const table = $('table#rankigns');
        if (table.length > 0) {
            table.find('a[href*="/fiis/"]').each((i, el) => {
                const ticker = $(el).attr('href').split('/').filter(Boolean).pop().toUpperCase();
                if (/^[A-Z]{4}11$/.test(ticker)) { // Only 11-ended tickers for infra usually
                    if (!tickers.includes(ticker)) tickers.push(ticker);
                }
            });
        }

        // If table ID is different or not found, try a more specific fallback (only items with 'logo' class in parent)
        if (tickers.length === 0) {
            $('a[href*="/fiis/"]').each((i, el) => {
                const parent = $(el).parent();
                if (parent.hasClass('logo') || parent.hasClass('name')) {
                    const ticker = $(el).attr('href').split('/').filter(Boolean).pop().toUpperCase();
                    if (/^[A-Z]{4}11$/.test(ticker) && !tickers.includes(ticker)) {
                        tickers.push(ticker);
                    }
                }
            });
        }

        console.log(`✅ Found ${tickers.length} FI-Infra tickers.`);
    } catch (err) {
        console.error('❌ Error discovering FI-Infra tickers:', err.message);
        // Minimal fallback list if scraping fails completely
        tickers = KNOWN_INFRAS;
    }

    // Fetch details for each ticker
    console.log(`📡 Fetching detailed data for ${tickers.length} FI-Infra assets...`);
    const results = [];
    for (const ticker of tickers) {
        try {
            const data = await getFiiMetadata(ticker);
            if (data.price > 0) {
                results.push(data);
            }
        } catch (e) {
            console.warn(`⚠️ Failed to fetch ${ticker}: ${e.message}`);
        }
    }

    // Attempt to get Selic for scoring
    let selic = selicParam;
    if (!selic) {
        selic = 12.75;
        try {
            const selicResponse = await axios.get('https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json');
            selic = parseFloat(selicResponse.data[0]?.valor || 12.75);
        } catch (e) { }
    }

    return results.map(f => {
        // Scoring logic for Infra
        let score = 5;
        if (f.dy > selic) score += 2;
        if (f.p_vp < 1.0) score += 2;
        if (f.p_vp < 0.95) score += 1;
        if (f.dy > 15) score += 1;
        if (f.dy < 8) score -= 2;

        const strategies = [];
        if (f.dy > (selic - 1) && f.p_vp < 1.05) strategies.push('INFRA_INCOME');
        if (f.dy > 12) strategies.push('DIVIDEND');

        const magicNumber = f.dy > 0 ? Math.ceil(1200 / f.dy) : 9999;
        const magicCost = magicNumber * f.price;

        return {
            ...f,
            segment: "Infraestrutura",
            type: "INFRA",
            score: Math.max(0, Math.min(10, score)),
            strategies,
            magicNumber,
            magicCost,
            selic,
            num_properties: 0,
            vacancy: 0,
            liquidity: f.liquidity || 500000,
            market_cap: 500000000 // Placeholder
        };
    });
}

module.exports = { getFIInfra };
