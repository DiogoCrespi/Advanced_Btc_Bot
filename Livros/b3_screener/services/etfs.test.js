const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const axios = require('axios');
const { getETFs } = require('./etfs');

describe('ETFs Service', () => {
    let originalGet;

    beforeEach(() => {
        originalGet = axios.get;
    });

    afterEach(() => {
        axios.get = originalGet;
    });

    test('getETFs should fetch and parse ETFs correctly while preserving order', async () => {
        axios.get = async (url) => {
            if (url === 'https://investidor10.com.br/etfs/') {
                return {
                    data: `
                        <div id="rankings">
                            <a href="/etfs/ivvb11/">IVVB11</a>
                            <a href="/etfs/bova11/">BOVA11</a>
                            <a href="/etfs/smal11/">SMAL11</a>
                        </div>
                    `
                };
            }
            if (url.includes('investidor10.com.br/etfs/')) {
                const ticker = url.split('/').filter(Boolean).pop().toUpperCase();
                // Simulate some delay for the first item to ensure parallel processing order doesn't mess up results
                if (ticker === 'IVVB11') await new Promise(r => setTimeout(r, 100));

                let price = '100,00';
                if (ticker === 'IVVB11') price = '250,50';
                else if (ticker === 'BOVA11') price = '110,20';

                return {
                    data: `<div class="cotacao">R$ ${price}</div>`
                };
            }
            if (url.includes('query1.finance.yahoo.com')) {
                return {
                    data: {
                        chart: {
                            result: [{
                                meta: {
                                    regularMarketVolume: 1000000,
                                    fiftyTwoWeekHigh: 300,
                                    fiftyTwoWeekLow: 200,
                                    regularMarketPrice: 250
                                }
                            }]
                        }
                    }
                };
            }
            return { data: '' };
        };

        const etfs = await getETFs();

        assert.strictEqual(etfs.length, 3);

        // Check order
        assert.strictEqual(etfs[0].ticker, 'IVVB11');
        assert.strictEqual(etfs[1].ticker, 'BOVA11');
        assert.strictEqual(etfs[2].ticker, 'SMAL11');

        // Check data
        assert.strictEqual(etfs[0].price, 250.5);
        assert.strictEqual(etfs[1].price, 110.2);
        assert.strictEqual(etfs[2].price, 100.0);
    });

    test('getETFs should handle missing data gracefully', async () => {
        axios.get = async (url) => {
            if (url === 'https://investidor10.com.br/etfs/') {
                return {
                    data: `
                        <div id="rankings">
                            <a href="/etfs/fail11/">FAIL11</a>
                        </div>
                    `
                };
            }
            if (url.includes('investidor10.com.br/etfs/')) {
                return { data: 'No price here' };
            }
            if (url.includes('query1.finance.yahoo.com')) {
                return { data: { chart: { result: [] } } };
            }
            return { data: '' };
        };

        const etfs = await getETFs();
        // Since price is 0 and it's filtered out, length should be 0
        assert.strictEqual(etfs.length, 0);
    });
});
