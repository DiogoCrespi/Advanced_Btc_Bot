const { test, describe, before, after, beforeEach } = require('node:test');
const assert = require('node:assert');
const BrapiStockAdapter = require('./brapi-stock-adapter');

describe('BrapiStockAdapter', () => {
    describe('transformStock', () => {
        const adapter = new BrapiStockAdapter();

        test('should correctly transform a complete stock object', () => {
            const input = {
                symbol: 'PETR4',
                regularMarketPrice: 35.50,
                averageDailyVolume10Day: 1000000,
                summaryProfile: {
                    trailingPE: 5.5,
                    priceToBook: 1.2,
                    priceToSalesTrailing12Months: 0.8,
                    dividendYield: 0.155, // 15.5%
                    enterpriseToEbitda: 3.5,
                    ebitdaMargins: 0.45, // 45%
                    profitMargins: 0.25, // 25%
                    returnOnAssets: 0.12,
                    returnOnEquity: 0.30, // 30%
                    debtToEquity: 0.6,
                    earningsQuarterlyGrowth: 0.05 // 5%
                }
            };

            const expected = {
                ticker: 'PETR4',
                cotacao: 35.50,
                pl: 5.5,
                p_vp: 1.2,
                psr: 0.8,
                dividend_yield: 15.5,
                ev_ebit: 3.5,
                mrg_ebit: 45,
                mrg_liq: 25,
                roic: 0.12,
                roe: 30,
                liq_2meses: 1000000,
                div_br_patrim: 0.6,
                cresc_5a: 5
            };

            const result = adapter.transformStock(input);
            assert.deepStrictEqual(result, expected);
        });

        test('should handle missing summaryProfile by using defaults', () => {
            const input = {
                symbol: 'VALE3',
                regularMarketPrice: 70.00
            };

            const result = adapter.transformStock(input);

            assert.strictEqual(result.ticker, 'VALE3');
            assert.strictEqual(result.cotacao, 70.00);
            assert.strictEqual(result.pl, 0);
            assert.strictEqual(result.p_vp, 0);
            assert.strictEqual(result.dividend_yield, 0);
            assert.strictEqual(result.roe, 0);
        });

        test('should handle missing fields within summaryProfile', () => {
            const input = {
                symbol: 'ITUB4',
                regularMarketPrice: 25.00,
                summaryProfile: {
                    trailingPE: 8.0
                    // other fields missing
                }
            };

            const result = adapter.transformStock(input);

            assert.strictEqual(result.ticker, 'ITUB4');
            assert.strictEqual(result.pl, 8.0);
            assert.strictEqual(result.p_vp, 0);
            assert.strictEqual(result.mrg_ebit, 0);
        });

        test('should correctly convert decimal fields to percentages', () => {
            const input = {
                symbol: 'ABEV3',
                summaryProfile: {
                    dividendYield: 0.0525,
                    ebitdaMargins: 0.321,
                    profitMargins: 0.187,
                    returnOnEquity: 0.154,
                    earningsQuarterlyGrowth: 0.082
                }
            };

            const result = adapter.transformStock(input);

            assert.strictEqual(result.dividend_yield, 5.25);
            assert.strictEqual(result.mrg_ebit, 32.1);
            assert.strictEqual(result.mrg_liq, 18.7);
            assert.strictEqual(result.roe, 15.4);
            assert.strictEqual(result.cresc_5a, 8.2);
        });

        test('should return null if transformation fails unexpectedly', () => {
            const result = adapter.transformStock(null);
            assert.strictEqual(result, null);
        });
    });

    describe('getStocks', () => {
        let originalFetch;
        let fetchCalls = [];

        before(() => {
            originalFetch = global.fetch;
        });

        after(() => {
            global.fetch = originalFetch;
        });

        beforeEach(() => {
            fetchCalls = [];
            global.fetch = async (url) => {
                fetchCalls.push(url);
                if (url.includes('/quote/list')) {
                    // Return a list of 150 dummy stocks
                    const stocks = Array.from({ length: 150 }, (_, i) => ({
                        stock: `TEST${i}`,
                        name: `Test Stock ${i}`,
                        close: 10.0,
                        change: 0.0,
                        volume: 1000,
                        market_cap: 1000000,
                        logo: 'https://brapi.dev/favicon.ico',
                        sector: 'Technology'
                    }));
                    return {
                        ok: true,
                        json: async () => ({ stocks: stocks.map(s => s.stock) })
                    };
                } else if (url.includes('/quote/')) {
                    const tickerString = url.split('/quote/')[1].split('?')[0];
                    const tickers = tickerString.split(',');

                    return {
                        ok: true,
                        json: async () => ({
                            results: tickers.map(t => ({
                                symbol: t,
                                regularMarketPrice: 10.0,
                                summaryProfile: {}
                            }))
                        })
                    };
                }
                return { ok: false, status: 404 };
            };
        });

        test('should fetch stocks in batches', async () => {
            const adapter = new BrapiStockAdapter();
            const results = await adapter.getStocks();

            // Should return 150 stocks
            assert.strictEqual(results.length, 150, `Expected 150 stocks, got ${results.length}`);

            // Verify fetch calls
            // First call is for the list
            assert.ok(fetchCalls[0].includes('/quote/list'));

            // Subsequent calls should be for details
            // With batch size 75, we expect 2 batches (150 / 75 = 2)
            // Total fetch calls = 1 list + 2 details = 3

            // Count detail calls
            const detailCalls = fetchCalls.filter(url => url.includes('/quote/') && !url.includes('/quote/list'));
            assert.strictEqual(detailCalls.length, 2, `Expected 2 detail batches, got ${detailCalls.length}`);

            // Verify batch sizes in URLs
            detailCalls.forEach(url => {
                const tickers = url.split('/quote/')[1].split('?')[0].split(',');
                assert.ok(tickers.length <= 75, `Batch size ${tickers.length} exceeds 75`);
            });
        });
    });
});
