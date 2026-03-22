const { test, describe, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const axios = require('axios');
const { getPrivateBenchmarks } = require('./fixed_income');
const { _resetCache } = require('./economy');

describe('Fixed Income Service - getPrivateBenchmarks', () => {
    let originalGet;

    beforeEach(() => {
        originalGet = axios.get;
        if (_resetCache) {
            _resetCache();
        }
    });

    afterEach(() => {
        axios.get = originalGet;
    });

    test('should calculate benchmarks correctly when Selic > 8.5%', async () => {
        const benchmarks = await getPrivateBenchmarks(10.5);

        assert.strictEqual(benchmarks.length, 4);

        // CDI is Selic - 0.10
        assert.strictEqual(benchmarks[0].name, 'CDB 100% CDI');
        assert.strictEqual(benchmarks[0].rate, '10.40%');

        // LCI/LCA is CDI * 0.90
        assert.strictEqual(benchmarks[1].name, 'LCI/LCA 90% CDI');
        assert.strictEqual(benchmarks[1].rate, '9.36%');

        // Poupança for Selic > 8.5 is fixed 6.17
        assert.strictEqual(benchmarks[2].name, 'Poupança (Est.)');
        assert.strictEqual(benchmarks[2].rate, '6.17% + TR');

        // CDB Pré-fixado is Selic + 1.5
        assert.strictEqual(benchmarks[3].name, 'CDB Pré-fixado (Est.)');
        assert.strictEqual(benchmarks[3].rate, '12.00%');
    });

    test('should calculate benchmarks correctly when Selic <= 8.5% (e.g. 8.0%)', async () => {
        const benchmarks = await getPrivateBenchmarks(8.0);

        assert.strictEqual(benchmarks.length, 4);

        // CDI is Selic - 0.10
        assert.strictEqual(benchmarks[0].name, 'CDB 100% CDI');
        assert.strictEqual(benchmarks[0].rate, '7.90%');

        // LCI/LCA is CDI * 0.90
        assert.strictEqual(benchmarks[1].name, 'LCI/LCA 90% CDI');
        assert.strictEqual(benchmarks[1].rate, '7.11%');

        // Poupança for Selic <= 8.5 is Selic * 0.70
        assert.strictEqual(benchmarks[2].name, 'Poupança (Est.)');
        assert.strictEqual(benchmarks[2].rate, '5.60% + TR');

        // CDB Pré-fixado is Selic + 1.5
        assert.strictEqual(benchmarks[3].name, 'CDB Pré-fixado (Est.)');
        assert.strictEqual(benchmarks[3].rate, '9.50%');
    });

    test('should calculate benchmarks correctly when Selic is exactly 8.5%', async () => {
        const benchmarks = await getPrivateBenchmarks(8.5);

        assert.strictEqual(benchmarks.length, 4);

        // Poupança for Selic <= 8.5 is Selic * 0.70
        assert.strictEqual(benchmarks[2].name, 'Poupança (Est.)');
        assert.strictEqual(benchmarks[2].rate, '5.95% + TR');
    });

    test('should fetch Selic rate using economy module if selicParam is null', async () => {
        // Mock axios to return 11.75
        axios.get = async () => ({
            data: [{ data: '01/01/2024', valor: '11.75' }]
        });

        const benchmarks = await getPrivateBenchmarks();

        assert.strictEqual(benchmarks.length, 4);

        // CDI is Selic - 0.10 = 11.65
        assert.strictEqual(benchmarks[0].name, 'CDB 100% CDI');
        assert.strictEqual(benchmarks[0].rate, '11.65%');

        // Poupança for Selic > 8.5 is 6.17
        assert.strictEqual(benchmarks[2].name, 'Poupança (Est.)');
        assert.strictEqual(benchmarks[2].rate, '6.17% + TR');
    });

    test('should handle errors gracefully and return an empty array', async () => {
        // If we pass an object that doesn't have a `toFixed` method, it will trigger an error in the calculation logic
        const errorBenchmarks = await getPrivateBenchmarks({});
        assert.deepStrictEqual(errorBenchmarks, []);
    });
});
