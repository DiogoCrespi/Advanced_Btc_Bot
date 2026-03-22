
// services/stocks.js
const FundamentusStockAdapter = require('./adapters/fundamentus-stock-adapter');
const BrapiStockAdapter = require('./adapters/brapi-stock-adapter');
const { analyzeStock } = require('./logic/stock-rules');
const { getSelicRate } = require('./economy');

async function getBestStocks(selicParam = null, dependencies = {}) {
    // Inject dependencies for testing
    const {
        FundamentusAdapter = FundamentusStockAdapter,
        BrapiAdapter = BrapiStockAdapter,
        stockAnalyzer = analyzeStock,
        selicFetcher = getSelicRate
    } = dependencies;

    let rawStocks = [];

    // 1. Fetch Data (Adapter Pattern with Failover)
    try {
        console.log('📊 Attempting to fetch from Fundamentus...');
        const fundamentusAdapter = new FundamentusAdapter();
        rawStocks = await fundamentusAdapter.getStocks();
        console.log(`✅ Successfully fetched ${rawStocks.length} stocks from Fundamentus`);
    } catch (fundamentusError) {
        console.warn('⚠️  Fundamentus failed:', fundamentusError.message);
        console.log('🔄 Switching to Brapi.dev backup...');

        try {
            const brapiAdapter = new BrapiAdapter();
            rawStocks = await brapiAdapter.getStocks();
            console.log(`✅ Successfully fetched ${rawStocks.length} stocks from Brapi.dev`);
        } catch (brapiError) {
            console.error('❌ Both data sources failed!');
            console.error('Fundamentus:', fundamentusError.message);
            console.error('Brapi:', brapiError.message);
            return [];
        }
    }

    try {

        // 2. Get Context (Selic)
        let selic = selicParam;
        if (!selic) {
            const fetchedSelic = await selicFetcher();
            if (fetchedSelic !== null) {
                selic = fetchedSelic;
            } else {
                console.warn('⚠️  Could not fetch Selic, using default 12.75%.');
                selic = 12.75;
            }
        }

        // 3. Apply Business Logic (Strategy Pattern)
        const enrichedStocks = rawStocks
            .filter(s => s.liq_2meses > 200000) // Basic liquidity filter
            .map(s => stockAnalyzer(s, selic))   // Apply rules/scoring
            .filter(s => s.category !== null)   // Remove junk
            .sort((a, b) => {
                // Sort: STARS first, then by Score
                if (a.category === 'STAR' && b.category !== 'STAR') return -1;
                if (a.category !== 'STAR' && b.category === 'STAR') return 1;
                return b.score - a.score || b.dividend_yield - a.dividend_yield;
            });

        // CRITICAL: Differentiated liquidity for STARS vs OPPORTUNITIES
        // STARS need 300k+ (captures quality small caps), OPPORTUNITIES can have 200k+ (value investing tolerance)
        const stars = enrichedStocks.filter(s => s.category === 'STAR' && s.liq_2meses > 300000);
        const opportunities = enrichedStocks.filter(s => s.category === 'OPPORTUNITY');

        return [...stars, ...opportunities];

    } catch (error) {
        console.error('Error in stock analysis/filtering:', error.message);
        return [];
    }
}

module.exports = { getBestStocks };
