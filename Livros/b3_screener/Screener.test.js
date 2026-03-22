const { test, describe, beforeEach } = require('node:test');
const assert = require('node:assert');
const Screener = require('./Screener');

describe('Screener Configuration', () => {
    let screener;

    beforeEach(() => {
        screener = new Screener();
    });

    test('should initialize with default configuration', () => {
        const expectedConfig = {
            assetType: 'stock',
            minLiquidity: 0,
            minYield: 0,
            maxP_VP: 999,
            minP_VP: 0,
            excludedStrategies: [],
            minScore: 0,
            maxDebtEq: 999
        };
        assert.deepStrictEqual(screener.config, expectedConfig);
    });

    test('should set assetType correctly', () => {
        screener.assetType('FII');
        assert.strictEqual(screener.config.assetType, 'fii');

        screener.assetType('stock');
        assert.strictEqual(screener.config.assetType, 'stock');
    });

    test('should throw error for invalid assetType', () => {
        assert.throws(() => {
            screener.assetType('invalid');
        }, {
            message: 'Invalid asset type. Use "stock" or "fii".'
        });
    });

    test('should set minLiquidity correctly', () => {
        screener.minLiquidity(100000);
        assert.strictEqual(screener.config.minLiquidity, 100000);
    });

    test('should set minYield correctly', () => {
        screener.minYield(5);
        assert.strictEqual(screener.config.minYield, 5);
    });

    test('should set maxP_VP correctly', () => {
        screener.maxP_VP(1.5);
        assert.strictEqual(screener.config.maxP_VP, 1.5);
    });

    test('should set minP_VP correctly', () => {
        screener.minP_VP(0.5);
        assert.strictEqual(screener.config.minP_VP, 0.5);
    });

    test('should set maxDebtEq correctly', () => {
        screener.maxDebtEq(2.0);
        assert.strictEqual(screener.config.maxDebtEq, 2.0);
    });

    test('should set minScore correctly', () => {
        screener.minScore(80);
        assert.strictEqual(screener.config.minScore, 80);
    });

    test('should set excludedStrategies correctly', () => {
        const strategies = ['GROWTH', 'VALUE'];
        screener.excludeStrategies(strategies);
        assert.deepStrictEqual(screener.config.excludedStrategies, strategies);
    });

    test('should not update excludedStrategies if input is not an array', () => {
        screener.excludeStrategies('INVALID');
        assert.deepStrictEqual(screener.config.excludedStrategies, []);
    });

    test('should set save option correctly', () => {
        screener.save(false);
        assert.strictEqual(screener.config.shouldSave, false);

        screener.save(); // default true
        assert.strictEqual(screener.config.shouldSave, true);
    });

    test('should set economy parameters correctly', () => {
        const dollar = 5.2;
        const selic = 11.75;
        screener.setEconomy(dollar, selic);
        assert.deepStrictEqual(screener.config.economy, { dollar, selic });
    });

    test('should allow method chaining', () => {
        const result = screener
            .assetType('fii')
            .minLiquidity(50000)
            .minYield(6)
            .maxP_VP(1.2)
            .minP_VP(0.8)
            .maxDebtEq(1.5)
            .minScore(70)
            .excludeStrategies(['RISKY'])
            .save(false)
            .setEconomy(5.0, 10.5);

        assert.strictEqual(result, screener);

        assert.strictEqual(screener.config.assetType, 'fii');
        assert.strictEqual(screener.config.minLiquidity, 50000);
        assert.strictEqual(screener.config.minYield, 6);
        assert.strictEqual(screener.config.maxP_VP, 1.2);
        assert.strictEqual(screener.config.minP_VP, 0.8);
        assert.strictEqual(screener.config.maxDebtEq, 1.5);
        assert.strictEqual(screener.config.minScore, 70);
        assert.deepStrictEqual(screener.config.excludedStrategies, ['RISKY']);
        assert.strictEqual(screener.config.shouldSave, false);
        assert.deepStrictEqual(screener.config.economy, { dollar: 5.0, selic: 10.5 });
    });
});
