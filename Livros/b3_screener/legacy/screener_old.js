const { getBestStocks } = require('./services/stocks');
const { getBestFIIs } = require('./services/fiis');

class Screener {
    constructor() {
        this.config = {
            assetType: 'stock', // default
            minLiquidity: 0,
            minYield: 0,
            maxP_VP: 999,
            minP_VP: 0,
            excludedStrategies: [],
            minScore: 0,
            maxDebtEq: 999
        };
    }

    assetType(type) {
        if (!['stock', 'fii'].includes(type.toLowerCase())) {
            throw new Error('Invalid asset type. Use "stock" or "fii".');
        }
        this.config.assetType = type.toLowerCase();
        return this;
    }

    minLiquidity(value) {
        this.config.minLiquidity = value;
        return this;
    }

    minYield(value) {
        this.config.minYield = value;
        return this;
    }

    maxP_VP(value) {
        this.config.maxP_VP = value;
        return this;
    }

    minP_VP(value) {
        this.config.minP_VP = value;
        return this;
    }

    maxDebtEq(value) {
        this.config.maxDebtEq = value;
        return this;
    }

    minScore(value) {
        this.config.minScore = value;
        return this;
    }

    excludeStrategies(strategies) {
        if (Array.isArray(strategies)) {
            this.config.excludedStrategies = strategies;
        }
        return this;
    }

    save(shouldSave = true) {
        this.config.shouldSave = shouldSave;
        return this;
    }

    async run() {
        console.log(`\n🚀 Starting Screener for [${this.config.assetType.toUpperCase()}]...`);
        let assets = [];

        try {
            if (this.config.assetType === 'stock') {
                assets = await getBestStocks();
            } else if (this.config.assetType === 'fii') {
                assets = await getBestFIIs();
            }
        } catch (err) {
            console.error('Error fetching assets:', err);
            return [];
        }

        console.log(`📥 Initial fetch: ${assets.length} items.`);

        // Apply Filters
        const results = assets.filter(item => {
            // Standardize field names across stocks and FIIs where possible
            const itemLiquidity = item.liq_2meses || item.liquidity || 0;
            const itemYield = item.dividend_yield || item.dy || 0;
            const itemP_VP = item.p_vp || 0;
            const itemScore = item.score || 0;
            const itemDebt = item.div_brut_patr || 0; // Debt/Equity for stocks
            const itemStrategies = item.strategies || [item.category].filter(Boolean); // Strategies or Category

            // 1. Liquidity
            if (itemLiquidity < this.config.minLiquidity) return false;

            // 2. Dividend Yield
            if (itemYield < this.config.minYield) return false;

            // 3. P/VP Range
            if (itemP_VP > this.config.maxP_VP) return false;
            if (itemP_VP < this.config.minP_VP) return false;

            // 4. Debt (Stocks only usually)
            if (this.config.assetType === 'stock' && itemDebt > this.config.maxDebtEq) return false;

            // 5. Score
            if (itemScore < this.config.minScore) return false;

            // 6. Excluded Strategies
            if (this.config.excludedStrategies.length > 0) {
                const hasExcludedStrategy = itemStrategies.some(s => this.config.excludedStrategies.includes(s));
                if (hasExcludedStrategy) return false;
            }

            return true;
        });

        console.log(`✅ Filtered down to: ${results.length} items.`);

        if (this.config.shouldSave) {
            const { saveHistory } = require('./services/storage');
            saveHistory(results, this.config.assetType);
        }

        console.log('\n');
        return results;
    }
}

module.exports = Screener;
