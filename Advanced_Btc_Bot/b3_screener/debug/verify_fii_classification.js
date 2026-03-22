const { getFiiMetadata } = require('../services/investidor10');
const { getBestFIIs } = require('../services/fiis');

// Mock function to simulate getBestFIIs internal logic without fetching from Fundamentus
// We will create a "baseList" with minimal data
async function testClassification(ticker) {
    console.log(`\nTesting Classification for ${ticker}...`);

    // 1. Fetch real metadata
    const meta = await getFiiMetadata(ticker);
    console.log(`[Inv10 Data] Type: "${meta.type}", Segment: "${meta.segment}"`);

    // 2. Create raw FII object (simulating Fundamentus data)
    // We only need ticker for the matching logic mostly
    const rawFii = {
        ticker: ticker,
        segment: 'Lajes Corporativas', // Dummy Fundamentus segment
        liquidity: 5000000,
        dy: 10,
        p_vp: 0.95,
        price: 100
    };

    // 3. Run getBestFIIs with this single item and the metadata
    const metadataMap = { [ticker]: meta };
    const results = await getBestFIIs(metadataMap, [rawFii]);

    if (results.length > 0) {
        const classified = results[0];
        console.log(`[Result] Classified Type: ${classified.type}`);
        console.log(`[Result] Strategies: ${classified.strategies.join(', ')}`);
    } else {
        console.log('[Result] Filtered out (likely due to score/liquidity).');
    }
}

(async () => {
    const testCases = ['MXRF11', 'HGLG11', 'SNAG11', 'JURO11', 'KNRI11', 'VISC11'];
    for (const t of testCases) {
        await testClassification(t);
        // await new Promise(r => setTimeout(r, 200));
    }
})();
