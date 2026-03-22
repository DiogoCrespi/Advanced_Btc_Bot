
// adapters/brapi-stock-adapter.js

/**
 * Adapter for Brapi.dev API
 * Fetches stock data from the Brapi.dev Brazilian stocks API
 */
class BrapiStockAdapter {
    constructor() {
        this.baseUrl = 'https://brapi.dev/api';
    }

    async getStocks() {
        try {
            // Brapi.dev provides a list endpoint for all stocks
            // We'll fetch the list first, then get details for each
            const listResponse = await fetch(`${this.baseUrl}/quote/list`);

            if (!listResponse.ok) {
                throw new Error(`Brapi API error: ${listResponse.status}`);
            }

            const listData = await listResponse.json();
            const tickers = listData.stocks || [];

            // Fetch detailed fundamentals for all stocks
            // Brapi allows batch requests with comma-separated tickers
            const results = [];
            const BATCH_SIZE = 75; // Limit to avoid URL length issues

            for (let i = 0; i < tickers.length; i += BATCH_SIZE) {
                const batch = tickers.slice(i, i + BATCH_SIZE);
                const tickerString = batch.join(',');

                try {
                    const detailsResponse = await fetch(`${this.baseUrl}/quote/${tickerString}?fundamental=true`);

                    if (!detailsResponse.ok) {
                        console.warn(`Brapi details error for batch starting with ${batch[0]}: ${detailsResponse.status}`);
                        continue;
                    }

                    const detailsData = await detailsResponse.json();
                    if (detailsData.results) {
                        results.push(...detailsData.results);
                    }
                } catch (batchError) {
                    console.error(`Error fetching batch starting with ${batch[0]}:`, batchError.message);
                    // Continue with next batch
                }
            }

            // Transform Brapi format to our internal format
            return results.map(stock => this.transformStock(stock)).filter(s => s !== null);

        } catch (error) {
            console.error('Error in BrapiStockAdapter:', error.message);
            throw error;
        }
    }

    transformStock(brapiStock) {
        try {
            const fundamentals = brapiStock.summaryProfile || {};
            const price = brapiStock.regularMarketPrice || 0;

            // Brapi uses different field names, we need to map them
            return {
                ticker: brapiStock.symbol || '',
                cotacao: price,
                pl: fundamentals.trailingPE || 0,
                p_vp: fundamentals.priceToBook || 0,
                psr: fundamentals.priceToSalesTrailing12Months || 0,
                dividend_yield: Math.round((fundamentals.dividendYield || 0) * 100 * 100) / 100, // Brapi returns as decimal
                ev_ebit: fundamentals.enterpriseToEbitda || 0,
                mrg_ebit: Math.round((fundamentals.ebitdaMargins || 0) * 100 * 100) / 100,
                mrg_liq: Math.round((fundamentals.profitMargins || 0) * 100 * 100) / 100,
                roic: fundamentals.returnOnAssets || 0, // Approximation
                roe: Math.round((fundamentals.returnOnEquity || 0) * 100 * 100) / 100,
                liq_2meses: brapiStock.averageDailyVolume10Day || 0,
                div_br_patrim: fundamentals.debtToEquity || 0,
                cresc_5a: Math.round((fundamentals.earningsQuarterlyGrowth || 0) * 100 * 100) / 100 // Approximation
            };
        } catch (e) {
            console.warn(`Failed to transform stock ${brapiStock?.symbol || 'unknown'}:`, e.message);
            return null;
        }
    }
}

module.exports = BrapiStockAdapter;
