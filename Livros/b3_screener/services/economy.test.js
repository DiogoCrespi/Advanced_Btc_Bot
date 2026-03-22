const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const axios = require('axios');
const { getDollarRate, getSelicRate, DOLLAR_RATE_API_URL, SELIC_RATE_API_URL } = require('./economy');

describe('Economy Service', () => {
    let originalGet;
    let originalConsoleError;
    let consoleErrors = [];

    beforeEach(() => {
        originalGet = axios.get;
        originalConsoleError = console.error;
        consoleErrors = [];
        console.error = (...args) => consoleErrors.push(args);
    });

    afterEach(() => {
        axios.get = originalGet;
        console.error = originalConsoleError;
    });

    describe('getDollarRate', () => {
        test('should fetch and parse Dollar rate correctly', async () => {
            axios.get = async (url) => {
                if (url === DOLLAR_RATE_API_URL) {
                    return {
                        data: {
                            USDBRL: {
                                bid: '5.25'
                            }
                        }
                    };
                }
                throw new Error('Unexpected URL');
            };

            const rate = await getDollarRate();
            assert.strictEqual(rate, 5.25);
        });

        test('should return null and log error when fetching Dollar rate fails', async () => {
            axios.get = async () => {
                throw new Error('Network Error');
            };

            const rate = await getDollarRate();
            assert.strictEqual(rate, null);
            assert.strictEqual(consoleErrors.length, 1);
            assert.strictEqual(consoleErrors[0][0], 'Error fetching Dollar rate:');
            assert.strictEqual(consoleErrors[0][1], 'Network Error');
        });
    });

    describe('getSelicRate', () => {
        test('should fetch and parse Selic rate correctly', async () => {
            axios.get = async (url) => {
                if (url === SELIC_RATE_API_URL) {
                    return {
                        data: [
                            {
                                data: '06/02/2026',
                                valor: '10.75'
                            }
                        ]
                    };
                }
                throw new Error('Unexpected URL');
            };

            const rate = await getSelicRate();
            assert.strictEqual(rate, 10.75);
        });

        test('should return null and log error when fetching Selic rate fails', async () => {
            axios.get = async () => {
                throw new Error('API Error');
            };

            const rate = await getSelicRate();
            assert.strictEqual(rate, null);
            assert.strictEqual(consoleErrors.length, 1);
            assert.strictEqual(consoleErrors[0][0], 'Error fetching Selic rate:');
            assert.strictEqual(consoleErrors[0][1], 'API Error');
        });
    });
});
