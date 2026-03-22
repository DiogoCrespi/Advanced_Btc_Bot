
// adapters/fundamentus-stock-adapter.js
const cheerio = require('cheerio');

const FUNDAMENTUS_URL = 'https://www.fundamentus.com.br/resultado.php';

// Safe parse helper
const parseNumber = (text) => {
    if (!text) return 0;
    return parseFloat(text.replace(/\./g, '').replace(',', '.').replace('%', ''));
};

class FundamentusStockAdapter {
    async getStocks() {
        try {
            const response = await fetch(FUNDAMENTUS_URL, {
                headers: {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const html = await response.text();
            const $ = cheerio.load(html);
            const stocks = [];

            $('#resultado tbody tr').each((i, el) => {
                const tds = $(el).find('td');
                const stock = {
                    ticker: $(tds[0]).text().trim(),
                    cotacao: parseNumber($(tds[1]).text().trim()),
                    pl: parseNumber($(tds[2]).text().trim()),
                    p_vp: parseNumber($(tds[3]).text().trim()),
                    psr: parseNumber($(tds[4]).text().trim()), // Column 4 is PSR
                    dividend_yield: parseNumber($(tds[5]).text().trim()),
                    ev_ebit: parseNumber($(tds[10]).text().trim()),
                    mrg_ebit: parseNumber($(tds[12]).text().trim()),
                    mrg_liq: parseNumber($(tds[13]).text().trim()),
                    roic: parseNumber($(tds[15]).text().trim()),
                    roe: parseNumber($(tds[16]).text().trim()),
                    liq_2meses: parseNumber($(tds[17]).text().trim()),
                    div_br_patrim: parseNumber($(tds[19]).text().trim()),
                    cresc_5a: parseNumber($(tds[20]).text().trim())
                };

                // CRITICAL FIX: Calculate Payout Ratio in 0-100 scale
                // Formula: Payout = (Dividend per Share / Earnings per Share) * 100
                // Simplified: Payout = (DY% * P/L)
                // Example: DY 32.61%, P/L 7.65 -> Payout = 32.61 * 7.65 = 249.46%
                // DO NOT divide by 100 - we want 249, not 2.49!
                if (stock.pl > 0 && stock.dividend_yield > 0) {
                    stock.payout = stock.dividend_yield * stock.pl; // Result in 0-100+ scale
                } else {
                    stock.payout = 0;
                }

                stocks.push(stock);
            });

            return stocks;

        } catch (error) {
            console.error('Error in FundamentusAdapter:', error.message);
            throw error; // Propagate up for failover
        }
    }
}

module.exports = FundamentusStockAdapter;
