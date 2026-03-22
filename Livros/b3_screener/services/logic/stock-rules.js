
// logic/stock-rules.js

/**
 * Analyzes a single stock and attaches strategies, scores, and categories.
 * @param {Object} s - Raw stock data (ticker, pl, p_vp, etc.)
 * @param {number} selic - Current Selic rate
 * @returns {Object} Enriched stock object
 */
function analyzeStock(s, selic) {
    // Robustness: Default selic if missing
    const safeSelic = (selic !== null && selic !== undefined && !isNaN(selic)) ? selic : 11.75;
    const YIELD_THRESHOLD = Math.max(6, safeSelic * 0.5);

    // Robustness: Ensure numeric values for calculations
    const cotacao = s.cotacao || 0;
    const pl = s.pl || 0;
    const p_vp = s.p_vp || 0;
    const dividend_yield = s.dividend_yield || 0;

    // Graham Fair Value
    let graham_fair_price = 0;
    if (pl > 0 && p_vp > 0) {
        graham_fair_price = cotacao * Math.sqrt(22.5 / (pl * p_vp));
    }
    const upside = (graham_fair_price > 0 && cotacao > 0) ? ((graham_fair_price - cotacao) / cotacao) * 100 : 0;

    // Bazin Price (Ceiling Price @ YIELD_THRESHOLD)
    const dps = (dividend_yield / 100) * cotacao;
    const bazin_price = YIELD_THRESHOLD > 0 ? dps / (YIELD_THRESHOLD / 100) : 0;
    const bazin_upside = (bazin_price > 0 && cotacao > 0) ? ((bazin_price - cotacao) / cotacao) * 100 : 0;

    // --- STRATEGY CLASSIFICATION ---
    const strategies = [];

    // 💎 Quality (Compounders): High ROE, Safe, Profitable, Good Margins, Growing
    // IMPROVED: Flexible ROIC logic to capture more quality companies
    // Option 1: ROE > 15 AND ROIC > 10 (capital-intensive companies like utilities)
    // Option 2: ROE > 12 AND ROIC > 15 (high efficiency companies)
    if (s.mrg_liq > 10 && s.div_br_patrim < 1 && s.cresc_5a > 5) {
        if ((s.roe > 15 && s.roic > 10) || (s.roe > 12 && s.roic > 15)) {
            strategies.push('QUALITY');
        }
    }

    // 💰 Dividends: High Yield, Low Risk, Sustainable
    // CRITICAL FIX: Perenne detection uses HIGH MARGIN, not low debt
    // Utilities (TAEE11, EGIE3) have high debt but predictable margins (15%+)
    // Insurers (BBSE3) have low debt but also high margins
    const isLikelyPerenne = s.mrg_liq > 15 && s.roe > 12; // High margin + stable ROE = Utility/Insurance
    const maxPayout = isLikelyPerenne ? 100 : 90;

    if (s.dividend_yield > YIELD_THRESHOLD && s.mrg_liq > 10 && s.cresc_5a > 0) {
        if (!s.payout || s.payout <= maxPayout) {
            strategies.push('DIVIDEND');
        }
    }

    // 📉 Discount/Value: Cheap P/L and P/VP
    if (s.pl > 0 && s.pl < 10 && s.p_vp > 0 && s.p_vp < 1.0) {
        strategies.push('VALUE');
    }

    // 🚀 Growth: High Revenue CAGR
    if (s.cresc_5a > 15 && s.roe > 10) {
        strategies.push('GROWTH');
    }

    // 🪄 Magic Formula (Greenblatt-ish)
    if (s.roic > 15 && s.ev_ebit > 0 && s.ev_ebit < 10) {
        strategies.push('MAGIC');
    }

    // 🐢 Bazin Safe (Legacy + New)
    if (s.dividend_yield > 6 && s.div_br_patrim < 1 && s.liq_2meses > 100000 && s.cresc_5a > -5) {
        strategies.push('BAZIN');
    }

    // --- SCORING SYSTEM (0-10) ---
    let score = 0;

    // Valuation
    if (s.pl < 10 && s.pl > 0) score++;
    if (s.p_vp < 1.0 && s.p_vp > 0) score++;
    if (s.ev_ebit < 8 && s.ev_ebit > 0) score++;

    // Valuation (PSR)
    if (s.psr < 2.0 && s.psr > 0) score++;

    // Efficiency & Profitability (Graduated ROE scoring)
    if (s.roe > 15) score += 2; // Excellent ROE
    else if (s.roe > 10) score += 1; // Good ROE (mature sectors)
    if (s.roic > 15) score++;
    if (s.mrg_liq > 10) score++;

    // Growth & PEG (Peter Lynch)
    const peg_ratio = (s.pl > 0 && s.cresc_5a > 0) ? (s.pl / s.cresc_5a) : 999;
    if (peg_ratio < 0.5) score += 2; // Super bargain (Peter Lynch "dream stock")
    else if (peg_ratio < 1) score++; // Fair value growth

    // Dividends (Capped at 16%)
    let effectiveDy = s.dividend_yield;
    if (effectiveDy > 16) {
        effectiveDy = 16;
        strategies.push('HIGH_VOLATILITY'); // Alert tag for extremely high yields
    }
    if (effectiveDy > YIELD_THRESHOLD) score++;

    // Trend / Innovation Check (Proxy: Revenue contraction 5y)
    // "Lucro Atual < Lucro 5 Anos Atrás" -> Using Revenue Growth < 0 as proxy
    if (s.cresc_5a < 0) {
        score -= 3;
    }

    // Health
    if (s.div_br_patrim < 1) score++;
    if (s.liq_2meses > 1000000) score++; // Liquidity Bonus

    // Upside Potential
    if (upside > 25 || bazin_upside > 20) score++;

    // Payout Ratio (Dividend Sustainability) - CRITICAL FIX: Stronger penalties
    if (s.payout > 0) {
        if (s.payout >= 30 && s.payout <= 60) score += 2; // Ideal range
        else if (s.payout > 60 && s.payout <= 80) score += 1; // Acceptable
        else if (s.payout > 150) score -= 5; // Red flag (likely capital return, not dividend)
        else if (s.payout > 100) score -= 4; // Unsustainable (paying more than earning)
        else if (s.payout > 90) score -= 2; // High risk
        else if (s.payout > 80 && !isLikelyPerenne) score -= 1; // Risky for non-perennes
    }

    // Cap score at 10
    score = Math.min(score, 10);

    // Determine Main Category for UI (Star vs Opportunity)
    let category = null;

    // CRITICAL: Disqualify from STAR if payout > 100% (likely one-time distribution)
    const isUnsustainablePayout = s.payout > 100;

    if ((score >= 7 || strategies.length >= 3) && !isUnsustainablePayout) {
        category = 'STAR';
    } else {
        // Refined Opportunity Logic
        if (s.pl > 0 && s.div_br_patrim < 2.5 && (s.roe > 5 || (s.dividend_yield > 4))) {
            if (s.p_vp < 0.95 || s.pl < 9 || s.ev_ebit < 10) {
                category = 'OPPORTUNITY';
            }
        }
    }

    // Turnaround Candidates context
    if (s.pl < 0 && s.mrg_ebit > 0 && s.cotacao > 2) {
        strategies.push('TURNAROUND');
        if (!category) category = 'OPPORTUNITY';
    }

    return {
        ...s,
        graham_price: graham_fair_price,
        upside,
        bazin_price,
        bazin_upside,
        selic,
        score,
        strategies,
        category,
        peg_ratio
    };
}

module.exports = { analyzeStock };
