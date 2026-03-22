const { test, describe } = require('node:test');
const assert = require('node:assert');
const { analyzeStock } = require('./stock-rules');

describe('stock-rules logic', () => {
    describe('analyzeStock', () => {
        const defaultSelic = 10;
        const defaultStock = {
            ticker: 'TEST3',
            cotacao: 20,
            pl: 10,
            p_vp: 1,
            psr: 1,
            dividend_yield: 5,
            ev_ebit: 5,
            mrg_ebit: 20,
            mrg_liq: 15,
            roic: 12,
            roe: 14,
            liq_2meses: 2000000,
            div_br_patrim: 0.5,
            cresc_5a: 10,
            payout: 50
        };

        test('should calculate Graham Fair Value correctly', () => {
            // graham = cotacao * sqrt(22.5 / (pl * p_vp))
            // 20 * sqrt(22.5 / (10 * 1)) = 20 * sqrt(2.25) = 20 * 1.5 = 30
            const result = analyzeStock(defaultStock, defaultSelic);
            assert.strictEqual(result.graham_price, 30);
            assert.strictEqual(result.upside, 50); // (30-20)/20 * 100 = 50%
        });

        test('should handle zero or negative P/L or P/VP in Graham calculation', () => {
            const stockPLZero = { ...defaultStock, pl: 0 };
            assert.strictEqual(analyzeStock(stockPLZero, defaultSelic).graham_price, 0);

            const stockPLNeg = { ...defaultStock, pl: -5 };
            assert.strictEqual(analyzeStock(stockPLNeg, defaultSelic).graham_price, 0);

            const stockPVPZero = { ...defaultStock, p_vp: 0 };
            assert.strictEqual(analyzeStock(stockPVPZero, defaultSelic).graham_price, 0);
        });

        test('should calculate Bazin Price correctly', () => {
            // YIELD_THRESHOLD = max(6, 10 * 0.5) = 6
            // dps = (5/100) * 20 = 1
            // bazin_price = 1 / (6/100) = 16.666...
            const result = analyzeStock(defaultStock, defaultSelic);
            assert.ok(Math.abs(result.bazin_price - 16.666) < 0.01);
            assert.ok(Math.abs(result.bazin_upside - (-16.666)) < 0.01);
        });

        test('should use 6% as minimum Bazin yield threshold', () => {
            const lowSelic = 4; // threshold = max(6, 2) = 6
            const result = analyzeStock(defaultStock, lowSelic);
            assert.ok(Math.abs(result.bazin_price - 16.666) < 0.01);
        });

        test('should use half of Selic if it is above 12%', () => {
            const highSelic = 14; // threshold = max(6, 7) = 7
            // dps = 1, bazin = 1 / 0.07 = 14.28
            const result = analyzeStock(defaultStock, highSelic);
            assert.ok(Math.abs(result.bazin_price - 14.28) < 0.01);
        });

        describe('Strategies', () => {
            test('should identify QUALITY stocks', () => {
                const qualityStock = {
                    ...defaultStock,
                    mrg_liq: 11,
                    div_br_patrim: 0.8,
                    cresc_5a: 6,
                    roe: 16,
                    roic: 11
                };
                const result = analyzeStock(qualityStock, defaultSelic);
                assert.ok(result.strategies.includes('QUALITY'));
            });

            test('should identify DIVIDEND stocks', () => {
                const dividendStock = {
                    ...defaultStock,
                    dividend_yield: 8, // > threshold 6
                    mrg_liq: 11,
                    cresc_5a: 1,
                    payout: 80
                };
                const result = analyzeStock(dividendStock, defaultSelic);
                assert.ok(result.strategies.includes('DIVIDEND'));
            });

            test('should identify VALUE stocks', () => {
                const valueStock = {
                    ...defaultStock,
                    pl: 8,
                    p_vp: 0.8
                };
                const result = analyzeStock(valueStock, defaultSelic);
                assert.ok(result.strategies.includes('VALUE'));
            });

            test('should identify GROWTH stocks', () => {
                const growthStock = {
                    ...defaultStock,
                    cresc_5a: 16,
                    roe: 11
                };
                const result = analyzeStock(growthStock, defaultSelic);
                assert.ok(result.strategies.includes('GROWTH'));
            });

            test('should identify MAGIC stocks', () => {
                const magicStock = {
                    ...defaultStock,
                    roic: 16,
                    ev_ebit: 8
                };
                const result = analyzeStock(magicStock, defaultSelic);
                assert.ok(result.strategies.includes('MAGIC'));
            });

            test('should identify BAZIN safe stocks', () => {
                const bazinSafeStock = {
                    ...defaultStock,
                    dividend_yield: 7,
                    div_br_patrim: 0.5,
                    liq_2meses: 200000,
                    cresc_5a: 1
                };
                const result = analyzeStock(bazinSafeStock, defaultSelic);
                assert.ok(result.strategies.includes('BAZIN'));
            });

            test('should identify TURNAROUND stocks', () => {
                const turnaroundStock = {
                    ...defaultStock,
                    pl: -5,
                    mrg_ebit: 5,
                    cotacao: 5
                };
                const result = analyzeStock(turnaroundStock, defaultSelic);
                assert.ok(result.strategies.includes('TURNAROUND'));
            });
        });

        describe('Scoring System', () => {
            test('should accumulate points for various metrics', () => {
                const greatStock = {
                    ticker: 'GOOD3',
                    cotacao: 10,
                    pl: 5,
                    p_vp: 0.5,
                    ev_ebit: 4,
                    psr: 1,
                    roe: 12,
                    roic: 10,
                    mrg_liq: 15,
                    dividend_yield: 7,
                    cresc_5a: 10,
                    div_br_patrim: 0.5,
                    liq_2meses: 2000000,
                    payout: 40
                };
                const result = analyzeStock(greatStock, defaultSelic);
                assert.strictEqual(result.score, 10);
            });

            test('should penalize negative growth', () => {
                const badGrowthStock = { ...defaultStock, cresc_5a: -10 };
                const resultNormal = analyzeStock(defaultStock, defaultSelic);
                const resultBad = analyzeStock(badGrowthStock, defaultSelic);
                assert.strictEqual(resultBad.score, resultNormal.score - 3);
            });

            test('should penalize unsustainable payout', () => {
                const unsustainableStock = { ...defaultStock, payout: 110 };
                const result = analyzeStock(unsustainableStock, defaultSelic);
                const normalResult = analyzeStock(defaultStock, defaultSelic);
                // payout 50 gives +2. payout 110 gives -4. Difference is -6.
                assert.strictEqual(result.score, normalResult.score - 6);
            });
        });

        describe('Category', () => {
            test('should assign STAR category for high scoring stocks', () => {
                const starStock = {
                    ...defaultStock,
                    roe: 20,
                    roic: 20,
                    pl: 5,
                    p_vp: 0.8
                };
                const result = analyzeStock(starStock, defaultSelic);
                assert.strictEqual(result.category, 'STAR');
            });

            test('should NOT assign STAR if payout is unsustainable', () => {
                const highPayoutStock = {
                    ...defaultStock,
                    roe: 20,
                    payout: 110
                };
                const result = analyzeStock(highPayoutStock, defaultSelic);
                assert.notStrictEqual(result.category, 'STAR');
            });

            test('should assign OPPORTUNITY for decent but not star stocks', () => {
                const oppStock = {
                    ...defaultStock,
                    pl: 12,
                    p_vp: 1.5,
                    ev_ebit: 9,
                    psr: 2.5,
                    roe: 8,
                    roic: 8,
                    mrg_liq: 12,
                    liq_2meses: 500000,
                    div_br_patrim: 1.5,
                    cresc_5a: 5,
                    payout: 25,
                    dividend_yield: 5,
                    cotacao: 20
                };
                const result = analyzeStock(oppStock, defaultSelic);
                assert.strictEqual(result.category, 'OPPORTUNITY');
            });
        });

        test('should calculate PEG ratio correctly', () => {
            const result = analyzeStock(defaultStock, defaultSelic);
            assert.strictEqual(result.peg_ratio, 10 / 10);

            const noGrowthStock = { ...defaultStock, cresc_5a: 0 };
            assert.strictEqual(analyzeStock(noGrowthStock, defaultSelic).peg_ratio, 999);
        });

        describe('Detailed Strategy Rules', () => {
            describe('QUALITY Strategy', () => {
                test('should qualify via Capital Intensive path (ROE > 15, ROIC > 10)', () => {
                    const stock = {
                        ...defaultStock,
                        mrg_liq: 15, div_br_patrim: 0.5, cresc_5a: 6, // Base requirements
                        roe: 16, roic: 11
                    };
                    const result = analyzeStock(stock, defaultSelic);
                    assert.ok(result.strategies.includes('QUALITY'));
                });

                test('should qualify via High Efficiency path (ROE > 12, ROIC > 15)', () => {
                    const stock = {
                        ...defaultStock,
                        mrg_liq: 15, div_br_patrim: 0.5, cresc_5a: 6, // Base requirements
                        roe: 13, roic: 16
                    };
                    const result = analyzeStock(stock, defaultSelic);
                    assert.ok(result.strategies.includes('QUALITY'));
                });

                test('should fail if margins are too low', () => {
                    const stock = {
                        ...defaultStock,
                        mrg_liq: 10, // Threshold is > 10
                        div_br_patrim: 0.5, cresc_5a: 6,
                        roe: 20, roic: 20
                    };
                    const result = analyzeStock(stock, defaultSelic);
                    assert.ok(!result.strategies.includes('QUALITY'));
                });

                test('should fail if debt is too high', () => {
                    const stock = {
                        ...defaultStock,
                        mrg_liq: 15,
                        div_br_patrim: 1.0, // Threshold is < 1
                        cresc_5a: 6,
                        roe: 20, roic: 20
                    };
                    const result = analyzeStock(stock, defaultSelic);
                    assert.ok(!result.strategies.includes('QUALITY'));
                });
            });

            describe('DIVIDEND Strategy', () => {
                test('should detect HIGH_VOLATILITY if yield > 16%', () => {
                    const stock = {
                        ...defaultStock,
                        dividend_yield: 17
                    };
                    const result = analyzeStock(stock, defaultSelic);
                    assert.ok(result.strategies.includes('HIGH_VOLATILITY'));
                });

                test('should allow Perenne stocks (High Margin + Stable ROE) to have payout up to 100%', () => {
                    const perenneStock = {
                        ...defaultStock,
                        dividend_yield: 8, // > 6
                        mrg_liq: 16, // > 15 (Perenne condition)
                        roe: 13,     // > 12 (Perenne condition)
                        cresc_5a: 1,
                        payout: 95   // > 90 but <= 100
                    };
                    const result = analyzeStock(perenneStock, defaultSelic);
                    assert.ok(result.strategies.includes('DIVIDEND'), 'Should include DIVIDEND tag for perenne with 95% payout');
                });

                test('should disqualifiy Perenne stocks if payout > 100%', () => {
                    const perenneStock = {
                        ...defaultStock,
                        dividend_yield: 8,
                        mrg_liq: 16,
                        roe: 13,
                        cresc_5a: 1,
                        payout: 101
                    };
                    const result = analyzeStock(perenneStock, defaultSelic);
                    assert.ok(!result.strategies.includes('DIVIDEND'));
                });

                test('should disqualify standard stocks if payout > 90%', () => {
                    const standardStock = {
                        ...defaultStock,
                        dividend_yield: 8,
                        mrg_liq: 12, // Not perenne (< 15)
                        roe: 10,
                        cresc_5a: 1,
                        payout: 91
                    };
                    const result = analyzeStock(standardStock, defaultSelic);
                    assert.ok(!result.strategies.includes('DIVIDEND'));
                });
            });

            describe('Payout Scoring Penalties', () => {
                const baseScoreStock = {
                   ...defaultStock,
                   // Set baseline to predictable values to isolate scoring
                   pl: 12, p_vp: 1.2, ev_ebit: 10, psr: 3, // No valuation points
                   roe: 9, roic: 9, mrg_liq: 9, // No efficiency points
                   dividend_yield: 2, // No yield point
                   cresc_5a: 0, // No growth point
                   div_br_patrim: 2, liq_2meses: 50000, // No health points
                   payout: 0 // Reset payout
                };

                test('should give +2 for ideal payout (30-60)', () => {
                    const stock = { ...baseScoreStock, payout: 40 };
                    const result = analyzeStock(stock, defaultSelic);
                    // Base score 0 + 2 = 2
                    assert.strictEqual(result.score, 2);
                });

                test('should give +1 for acceptable payout (60-80)', () => {
                    const stock = { ...baseScoreStock, payout: 70 };
                    const result = analyzeStock(stock, defaultSelic);
                    assert.strictEqual(result.score, 1);
                });

                test('should penalize -1 for risky payout (80-90) if not perenne', () => {
                     const stock = { ...baseScoreStock, payout: 85, mrg_liq: 10 }; // Not perenne
                     const result = analyzeStock(stock, defaultSelic);
                     assert.strictEqual(result.score, -1);
                });

                test('should NOT penalize payout 80-90 if perenne', () => {
                     const stock = { ...baseScoreStock, payout: 85, mrg_liq: 16, roe: 13 }; // Perenne
                     // Perenne gets mrg_liq > 10 (+1) and roe > 10 (+1). Base score = 2.
                     // Payout > 80 check says: else if (s.payout > 80 && !isLikelyPerenne).
                     // So it should SKIP the penalty.
                     // Score should be 2.
                     const result = analyzeStock(stock, defaultSelic);
                     assert.strictEqual(result.score, 2);
                });

                test('should penalize -2 for high risk payout (>90)', () => {
                    const stock = { ...baseScoreStock, payout: 95 };
                    const result = analyzeStock(stock, defaultSelic);
                    assert.strictEqual(result.score, -2);
                });

                test('should penalize -4 for unsustainable payout (>100)', () => {
                    const stock = { ...baseScoreStock, payout: 105 };
                    const result = analyzeStock(stock, defaultSelic);
                    assert.strictEqual(result.score, -4);
                });

                test('should penalize -5 for extreme payout (>150)', () => {
                    const stock = { ...baseScoreStock, payout: 160 };
                    const result = analyzeStock(stock, defaultSelic);
                    assert.strictEqual(result.score, -5);
                });
            });
        });
    });

    describe('Edge Cases & Robustness', () => {
        test('should handle empty stock object gracefully', () => {
            const result = analyzeStock({}, 10);
            assert.strictEqual(result.graham_price, 0);
            assert.strictEqual(result.bazin_price, 0);
            assert.strictEqual(result.score, 0);
            assert.deepStrictEqual(result.strategies, []);
        });

        test('should use default Selic (11.75) if undefined or null', () => {
            // With default selic 11.75 -> threshold = max(6, 5.875) = 6
            // Stock with yield 7 should pass threshold
            const stock = { dividend_yield: 7, cotacao: 100 };
            const result = analyzeStock(stock, undefined);

            // bazin_price = dps / 0.06 = 7 / 0.06 = 116.66...
            assert.ok(result.bazin_price > 100);
            assert.strictEqual(result.bazin_upside > 0, true);

            const resultNull = analyzeStock(stock, null);
            assert.ok(resultNull.bazin_price > 100);
        });

        test('should handle missing numeric properties by defaulting to 0', () => {
            // Missing cotacao, pl, p_vp, dividend_yield
            const result = analyzeStock({ ticker: 'TEST' }, 10);
            assert.strictEqual(result.graham_price, 0);
            assert.strictEqual(result.bazin_price, 0);
            assert.strictEqual(result.upside, 0);
            assert.strictEqual(result.bazin_upside, 0);
        });

        test('should handle zero values preventing division by zero', () => {
            const stock = {
                cotacao: 10,
                pl: 0,
                p_vp: 0,
                dividend_yield: 0
            };
            const result = analyzeStock(stock, 10);

            // Graham: sqrt(22.5 / (0 * 0)) -> would be Infinity if not guarded
            // But code checks if (pl > 0 && p_vp > 0)
            assert.strictEqual(result.graham_price, 0);

            // Bazin: dps = 0. price = 0 / threshold = 0
            assert.strictEqual(result.bazin_price, 0);
        });

        test('should cap effective dividend yield at 16% for scoring', () => {
            // If yield is 20%, score should use 16% but strategies might tag HIGH_VOLATILITY
            const stock = {
                ticker: 'RISK11',
                cotacao: 10,
                dividend_yield: 20,
                mrg_liq: 15,
                cresc_5a: 5,
                payout: 50
            };
            const result = analyzeStock(stock, 10); // threshold 6%

            // Should have HIGH_VOLATILITY strategy
            assert.ok(result.strategies.includes('HIGH_VOLATILITY'));

            // Score check: yield > threshold (20 > 6) -> +1
            // But effectiveDy is capped at 16 internally for logic if any specific score depended on magnitude (none does directly, just threshold)
            // Strategy check:
            // dividend_yield > YIELD_THRESHOLD (20 > 6) -> valid for DIVIDEND strategy logic
            assert.ok(result.strategies.includes('DIVIDEND'));
        });

        test('should handle extreme payout ratios correctly in scoring', () => {
            const stock = { ticker: 'PAY1', payout: 200 };
            const result = analyzeStock(stock, 10);
            // Payout > 150 -> score -= 5
            // Base score 0. Score becomes -5. Min score is not clamped to 0? Code says score = Math.min(score, 10). It doesn't say max(score, 0).
            // Let's verify score can be negative.
            assert.ok(result.score <= 0);
        });
    });
});
