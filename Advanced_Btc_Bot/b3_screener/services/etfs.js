const axios = require('axios');
const cheerio = require('cheerio');

/**
 * Fetches detailed data for a single ETF
 * @param {string} ticker
 * @returns {Promise<Object|null>}
 */
async function fetchETFDetails(ticker) {
    try {
        const data = {
            ticker,
            price: 0,
            dy: 0,
            market_cap: 0,
            variation_12m: 0,
            liquidity: 0,
            high_52w: 0,
            low_52w: 0
        };

        // 1. Fetch Price from Investidor 10
        try {
            const detailUrl = `https://investidor10.com.br/etfs/${ticker.toLowerCase()}/`;
            const detailRes = await axios.get(detailUrl, {
                headers: { 'User-Agent': 'Mozilla/5.0' }
            });
            const $d = cheerio.load(detailRes.data);

            const cotacaoText = $d('.cotacao').text().trim();
            const priceMatch = cotacaoText.match(/R\$\s*([\d.,]+)/);
            if (priceMatch) {
                data.price = parseFloat(priceMatch[1].replace(/\./g, '').replace(',', '.')) || 0;
            }
        } catch (err) {
            console.error(`⚠️ Error fetching Investidor10 for ${ticker}: ${err.message}`);
        }

        // 2. Fetch Volume/High/Low from Yahoo Finance
        try {
            const yahooUrl = `https://query1.finance.yahoo.com/v8/finance/chart/${ticker}.SA?interval=1d&range=1d`;
            const yahooRes = await axios.get(yahooUrl, {
                headers: { 'User-Agent': 'Mozilla/5.0' }
            });
            const result = yahooRes.data.chart.result[0];
            if (result && result.meta) {
                data.liquidity = result.meta.regularMarketVolume || 0;
                data.high_52w = result.meta.fiftyTwoWeekHigh || 0;
                data.low_52w = result.meta.fiftyTwoWeekLow || 0;

                // Fallback price if Investidor10 failed
                if (data.price === 0 && result.meta.regularMarketPrice) {
                    data.price = result.meta.regularMarketPrice;
                }
            }
        } catch (err) {
            // Normalize error message (404 is common for some tickers)
            // const status = err.response ? err.response.status : 'Unknown';
        }

        return data.price > 0 ? data : null;
    } catch (err) {
        console.error(`❌ Error processing ${ticker}:`, err.message);
        return null;
    }
}

async function getETFs() {
    console.log('📡 Discovering ETFs from Investidor10...');
    const tickers = [];

    try {
        const response = await axios.get('https://investidor10.com.br/etfs/', {
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        });

        const $ = cheerio.load(response.data);

        // Find tickers in the rankings table
        const table = $('#rankings');
        if (table.length > 0) {
            table.find('a[href*="/etfs/"]').each((i, el) => {
                const ticker = $(el).attr('href').split('/').filter(Boolean).pop().toUpperCase();
                if (/^[A-Z0-9]{4,6}11$/.test(ticker)) {
                    if (!tickers.includes(ticker)) tickers.push(ticker);
                }
            });
        }

        // Fallback for cases where table ID might be different or missing
        if (tickers.length === 0) {
            $('a[href*="/etfs/"]').each((i, el) => {
                const ticker = $(el).attr('href').split('/').filter(Boolean).pop().toUpperCase();
                if (/^[A-Z0-9]{4,6}11$/.test(ticker)) {
                    if (!tickers.includes(ticker) && ticker !== 'ETFS') {
                        tickers.push(ticker);
                    }
                }
            });
        }

        console.log(`✅ Found ${tickers.length} ETF tickers.`);

        // Fetch details for each ETF
        const targetTickers = tickers.slice(0, 40); // Limit to top 40
        console.log(`📡 Fetching detailed data for ${targetTickers.length} ETFs...`);

        const CONCURRENCY_LIMIT = 5;
        const results = new Array(targetTickers.length);
        const queue = targetTickers.map((ticker, index) => ({ ticker, index }));

        const worker = async () => {
            while (queue.length > 0) {
                const item = queue.shift();
                const data = await fetchETFDetails(item.ticker);
                results[item.index] = data;
            }
        };

        const workers = [];
        for (let i = 0; i < Math.min(CONCURRENCY_LIMIT, targetTickers.length); i++) {
            workers.push(worker());
        }

        await Promise.all(workers);

        // Filter out null results (ETFs that failed or were invalid) while preserving order
        return results.filter(data => data !== null);

    } catch (error) {
        console.error('❌ Error discovering ETFs:', error.message);
        return [];
    }
}

module.exports = { getETFs };
