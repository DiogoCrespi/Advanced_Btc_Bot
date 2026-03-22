const fs = require('fs');
const { getDollarRate, getSelicRate } = require('./services/economy');
const { getBestStocks } = require('./services/stocks');
const { getBestFIIs } = require('./services/fiis');
const { getFIInfra } = require('./services/fi_infra');
const { getETFs } = require('./services/etfs');
const { getTesouroDirect, getPrivateBenchmarks } = require('./services/fixed_income');
const { getMultipleAssetMetadata } = require('./services/investidor10');
const { saveHistory } = require('./services/storage');

async function exportData() {
    console.log('🚀 Starting Data Export for B3 Screener...');

    try {
        // 1. Initial Data Fetch
        // Fetch Selic first to avoid redundant requests in parallel calls
        const selic = await getSelicRate();
        const [dollar, stocks, rawStandardFiis, rawInfraFiis, etfs, tesouro, privateFixed] = await Promise.all([
            getDollarRate(),
            getBestStocks(selic),
            getBestFIIs({}, null, selic), // Pass 1: Discovery from Fundamentus
            getFIInfra(selic),  // Pass 1: Discovery from hardcoded Infra list
            getETFs(),
            getTesouroDirect(),
            getPrivateBenchmarks(selic)
        ]);

        // 2. Combine all discovered FIIs to fetch metadata
        const combinedRaw = [...rawStandardFiis, ...rawInfraFiis];
        const allFiiTickers = [...new Set(combinedRaw.map(f => f.ticker))];

        // 3. Select top-ranked stocks to fetch metadata (to save time/requests)
        const stockTickers = stocks.slice(0, 50).map(s => s.ticker);
        const allTickers = [...allFiiTickers, ...stockTickers];

        console.log(`🔍 Found ${allFiiTickers.length} FIIs and ${stockTickers.length} sample stocks. Fetching verified metadata from Investidor 10...`);

        // 4. Fetch verified metadata from Investidor 10
        const metadataMap = await getMultipleAssetMetadata(allTickers, 150);

        // 5. Second Pass: Re-process the combined list through the business logic
        console.log('⚖️  Re-processing all FIIs/Infras with verified metadata...');
        const finalFiis = await getBestFIIs(metadataMap, combinedRaw, selic);

        // 6. Enrich stocks with metadata (Dividend Dates)
        const finalStocks = stocks.map(s => {
            const meta = metadataMap[s.ticker] || {};
            return {
                ...s,
                data_com: meta.data_com || null,
                data_pagamento: meta.data_pagamento || null
            };
        });

        const data = {
            updatedAt: new Date().toLocaleString('pt-BR'),
            economy: { dollar, selic },
            stocks: finalStocks,
            fiis: finalFiis,
            etfs,
            fixedIncome: {
                tesouro,
                private: privateFixed
            }
        };

        if (stocks.length === 0 && finalFiis.length === 0) {
            console.error('❌ CRITICAL: No data fetched (0 stocks, 0 FIIs). Aborting save to prevent overwriting with empty data.');
            process.exit(1);
        }

        const fileContent = `window.INVEST_DATA = ${JSON.stringify(data, null, 2)};`;
        fs.writeFileSync('data.js', fileContent);

        // --- Save History ---
        saveHistory(finalStocks, 'stock', { dollar, selic });
        saveHistory(finalFiis, 'fii', { dollar, selic });
        saveHistory(etfs, 'etf', { dollar, selic });
        saveHistory(data.fixedIncome, 'fixed', { dollar, selic });

        const stats = {
            total: finalFiis.length,
            infra: finalFiis.filter(f => f.type === 'INFRA').length,
            agro: finalFiis.filter(f => f.type === 'AGRO').length,
            papel: finalFiis.filter(f => f.type === 'PAPEL').length,
            tijolo: finalFiis.filter(f => f.type === 'TIJOLO').length,
            multi: finalFiis.filter(f => f.type === 'MULTI').length,
            etfs: etfs.length
        };

        console.log('✅ Data exported successfully!');
        console.log(`📊 Statistics: ${stats.total} FIIs, ${stats.etfs} ETFs (${stats.tijolo} Tijolo, ${stats.papel} Papel, ${stats.agro} Agro, ${stats.infra} Infra, ${stats.multi} Multi)`);

    } catch (error) {
        console.error('❌ Error exporting data:', error);
    }
}

exportData();
