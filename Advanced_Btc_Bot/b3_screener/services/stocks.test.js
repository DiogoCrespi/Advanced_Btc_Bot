
const { test, describe } = require('node:test');
const assert = require('node:assert');
const { getBestStocks } = require('./stocks');

describe('Stocks Service', () => {

    // Helper to create mock stocks
    const createMockStock = (ticker, overrides = {}) => ({
        ticker,
        liq_2meses: 500000,
        dividend_yield: 10,
        pl: 5,
        p_vp: 0.8,
        ...overrides
    });

    test('should fetch stocks from Fundamentus (primary) when successful', async () => {
        // Mocks
        class MockFundamentus {
            async getStocks() {
                return [createMockStock('PETR4')];
            }
        }

        class MockBrapi {
            async getStocks() {
                throw new Error('Should not be called');
            }
        }

        const mockAnalyze = (s) => ({ ...s, category: 'STAR', score: 10 });
        const mockSelic = async () => 10.0;

        const stocks = await getBestStocks(null, {
            FundamentusAdapter: MockFundamentus,
            BrapiAdapter: MockBrapi,
            stockAnalyzer: mockAnalyze,
            selicFetcher: mockSelic
        });

        assert.strictEqual(stocks.length, 1);
        assert.strictEqual(stocks[0].ticker, 'PETR4');
    });

    test('should failover to Brapi when Fundamentus fails', async () => {
         // Mocks
         class MockFundamentus {
            async getStocks() {
                throw new Error('Fundamentus Down');
            }
        }

        class MockBrapi {
            async getStocks() {
                return [createMockStock('VALE3')];
            }
        }

        const mockAnalyze = (s) => ({ ...s, category: 'OPPORTUNITY', score: 8 });
        const mockSelic = async () => 10.0;

        const stocks = await getBestStocks(null, {
            FundamentusAdapter: MockFundamentus,
            BrapiAdapter: MockBrapi,
            stockAnalyzer: mockAnalyze,
            selicFetcher: mockSelic
        });

        assert.strictEqual(stocks.length, 1);
        assert.strictEqual(stocks[0].ticker, 'VALE3');
    });

    test('should return empty array when both adapters fail', async () => {
        // Mocks
        class MockFundamentus {
           async getStocks() {
               throw new Error('Fundamentus Down');
           }
       }

       class MockBrapi {
           async getStocks() {
               throw new Error('Brapi Down');
           }
       }

       const stocks = await getBestStocks(null, {
           FundamentusAdapter: MockFundamentus,
           BrapiAdapter: MockBrapi
       });

       assert.deepStrictEqual(stocks, []);
   });

   test('should correctly sort and filter stocks (STARS > OPPORTUNITY)', async () => {
        // Mock Data
        const rawStocks = [
            createMockStock('STAR1'),
            createMockStock('OPP1'),
            createMockStock('JUNK1'), // Should be filtered out
            createMockStock('STAR2'),
            createMockStock('LOWLIQ', { liq_2meses: 1000 }) // Should be filtered out by initial filter
        ];

        class MockFundamentus {
            async getStocks() { return rawStocks; }
        }

        // Mock Logic
        const mockAnalyze = (s) => {
            if (s.ticker === 'STAR1') return { ...s, category: 'STAR', score: 9 };
            if (s.ticker === 'STAR2') return { ...s, category: 'STAR', score: 8 };
            if (s.ticker === 'OPP1') return { ...s, category: 'OPPORTUNITY', score: 9 };
            if (s.ticker === 'JUNK1') return { ...s, category: null, score: 0 };
            // Pass through LOWLIQ to see if it gets filtered before
            if (s.ticker === 'LOWLIQ') return { ...s, category: 'STAR', score: 10 };
            return { ...s, category: null }; // Fallback
        };

        const stocks = await getBestStocks(10.0, {
            FundamentusAdapter: MockFundamentus,
            stockAnalyzer: mockAnalyze,
            selicFetcher: async () => 10.0
        });

        // LOWLIQ should be gone (filtered before analyze)
        // JUNK1 should be gone (filtered after analyze)

        // Expected order: STARS (by score), then OPPORTUNITIES
        // STAR1 (9), STAR2 (8), OPP1 (9)

        assert.strictEqual(stocks.length, 3);
        assert.strictEqual(stocks[0].ticker, 'STAR1');
        assert.strictEqual(stocks[1].ticker, 'STAR2');
        assert.strictEqual(stocks[2].ticker, 'OPP1');
   });

   test('should filter out STARS with low liquidity (< 300k)', async () => {
         // STAR needs 300k, OPPORTUNITY needs 200k (but base filter is 200k)

         const rawStocks = [
            createMockStock('STAR_LOW_LIQ', { liq_2meses: 250000 }),
            createMockStock('STAR_HIGH_LIQ', { liq_2meses: 350000 }),
         ];

         class MockFundamentus {
             async getStocks() { return rawStocks; }
         }

         const mockAnalyze = (s) => ({ ...s, category: 'STAR' });

         const stocks = await getBestStocks(10.0, {
             FundamentusAdapter: MockFundamentus,
             stockAnalyzer: mockAnalyze,
             selicFetcher: async () => 10.0
         });

         assert.strictEqual(stocks.length, 1);
         assert.strictEqual(stocks[0].ticker, 'STAR_HIGH_LIQ');
   });
});
