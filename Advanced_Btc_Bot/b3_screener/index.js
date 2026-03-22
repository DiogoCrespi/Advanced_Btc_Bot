const Screener = require('./Screener');
const { getDollarRate, getSelicRate } = require('./services/economy');
const { getETFs } = require('./services/etfs');
const { getPrivateBenchmarks } = require('./services/fixed_income');
const fs = require('fs');

async function main() {
    console.log('--- B3 SCREENER DASHBOARD (New Architecture) ---\n');
    console.log('Fetching data... please wait.');

    // 1. Fetch Economy Data in Parallel
    const [dollar, selic, etfs, privateBenchmarks] = await Promise.all([
        getDollarRate(),
        getSelicRate(),
        getETFs(),
        getPrivateBenchmarks()
    ]);

    // 2. Run Screeners using Fluent Interface

    // Stocks
    console.log('\n--> Running Stock Screener...');
    const stockScreener = new Screener()
        .assetType('stock')
        .minLiquidity(100000) // Base liquidity filter
        .setEconomy(dollar, selic)
        .save(true); // Persist results

    const stocks = await stockScreener.run();

    // FIIs
    console.log('\n--> Running FII Screener...');
    const fiiScreener = new Screener()
        .assetType('fii')
        .minLiquidity(200000) // FII base liquidity
        .setEconomy(dollar, selic)
        .save(true); // Persist results

    const fiis = await fiiScreener.run();


    // 3. Display Dashboard

    console.log('================================================================================');
    console.log(` 🇧🇷 B3 DASHBOARD | 💵 USD: R$ ${dollar?.toFixed(2) || 'N/A'} | 📈 SELIC: ${selic || 'N/A'}% `);
    console.log('================================================================================\n');

    // --- EXPORT TO DATA.JS FOR FRONTEND ---
    try {
        const investData = {
            updatedAt: new Date().toLocaleString('pt-BR'),
            economy: { dollar, selic },
            stocks: stocks,
            fiis: fiis,
            etfs: etfs,
            fixedIncome: { private: privateBenchmarks }
        };

        if (stocks.length === 0 && fiis.length === 0) {
            console.error('❌ CRITICAL: No data fetched (0 stocks, 0 FIIs). Aborting save to prevent overwriting with empty data.');
            process.exit(1);
        }

        const fileContent = `window.INVEST_DATA = ${JSON.stringify(investData, null, 2)};`;
        fs.writeFileSync('data.js', fileContent);
        console.log('✅ Data exported successfully to data.js!');
    } catch (err) {
        console.error('Error exporting data:', err);
    }

    // --- STOCK DISPLAY ---
    const starStocks = stocks.filter(s => s.category === 'STAR');
    const opportunityStocks = stocks.filter(s => s.category === 'OPPORTUNITY');

    // STARS
    console.log('\n--- ⭐ TOP 10 STARS (Strict Quality + Growth + Income) ---');
    console.log('Criteria: Liquidity > 100k, ROE > 10%, CAGR > 5%, DY > 6%');
    console.log('-'.repeat(105));
    console.log(
        'Ticket'.padEnd(8) +
        'Price'.padEnd(9) +
        'P/VP'.padEnd(6) +
        'DY%'.padEnd(7) +
        'CAGR%'.padEnd(8) +
        'D/Eq'.padEnd(6) +
        'Graham'.padEnd(9) +
        'Bazin'.padEnd(9) +
        'Upside'.padEnd(8) +
        'EV/EBIT'.padEnd(8) +
        'Score'.padEnd(6) +
        'PSR'.padEnd(6) +
        'PEG'
    );
    console.log('-'.repeat(110));

    if (starStocks.length > 0) {
        starStocks.slice(0, 10).forEach(s => {
            console.log(
                s.ticker.padEnd(8) +
                s.cotacao.toFixed(2).padEnd(9) +
                s.p_vp.toFixed(2).padEnd(6) +
                (s.dividend_yield.toFixed(1) + '%').padEnd(7) +
                (s.cresc_5a.toFixed(1) + '%').padEnd(8) +
                s.div_br_patrim.toFixed(2).padEnd(6) +
                s.graham_price.toFixed(2).padEnd(9) +
                s.bazin_price.toFixed(2).padEnd(9) +
                (s.upside.toFixed(0) + '%').padEnd(8) +
                (s.ev_ebit ? s.ev_ebit.toFixed(2) : 'N/A').padEnd(8) +
                (s.score + '/9').padEnd(6) +
                (s.psr ? s.psr.toFixed(2) : 'N/A').padEnd(6) +
                ((s.peg_ratio && s.peg_ratio !== 999) ? s.peg_ratio.toFixed(2) : 'N/A')
            );
        });
    } else {
        console.log('No STARS found. Market is tough!');
    }
    console.log('\n');

    // OPPORTUNITIES
    console.log('--- 📈 OPPORTUNITIES (Profitable & Value) ---');
    console.log('Criteria: Profitable (P/L>0) OR Deep Value (P/VP<0.8). No Junk.');
    console.log('-'.repeat(105));
    console.log(
        'Ticket'.padEnd(8) +
        'Price'.padEnd(9) +
        'P/VP'.padEnd(6) +
        'DY%'.padEnd(7) +
        'CAGR%'.padEnd(8) +
        'D/Eq'.padEnd(6) +
        'Graham'.padEnd(9) +
        'Bazin'.padEnd(9) +
        'Upside'.padEnd(8) +
        'EV/EBIT'.padEnd(8) +
        'Score'.padEnd(6) +
        'PSR'.padEnd(6) +
        'PEG'
    );
    console.log('-'.repeat(110));

    if (opportunityStocks.length > 0) {
        opportunityStocks.forEach(s => {
            console.log(
                s.ticker.padEnd(8) +
                s.cotacao.toFixed(2).padEnd(9) +
                s.p_vp.toFixed(2).padEnd(6) +
                (s.dividend_yield.toFixed(1) + '%').padEnd(7) +
                (s.cresc_5a.toFixed(1) + '%').padEnd(8) +
                s.div_br_patrim.toFixed(2).padEnd(6) +
                s.graham_price.toFixed(2).padEnd(9) +
                s.bazin_price.toFixed(2).padEnd(9) +
                (s.upside.toFixed(0) + '%').padEnd(8) +
                (s.ev_ebit ? s.ev_ebit.toFixed(2) : 'N/A').padEnd(8) +
                (s.score + '/9').padEnd(6) +
                (s.psr ? s.psr.toFixed(2) : 'N/A').padEnd(6) +
                ((s.peg_ratio && s.peg_ratio !== 999) ? s.peg_ratio.toFixed(2) : 'N/A')
            );
        });
        console.log(`\nTotal Opportunities found: ${opportunityStocks.length}`);
    } else {
        console.log('No Opportunities found.');
    }
    console.log('\n');

    // --- FII DISPLAY ---
    console.log('--- 🏘️  TOP FIIs (Real Estate) ---');
    console.log('Criteria: Score System (0-10), Type Separation, Safety Checks.');
    console.log('-'.repeat(115));
    console.log(
        'Ticker'.padEnd(8) +
        'Type'.padEnd(10) +
        'Price'.padEnd(9) +
        'P/VP'.padEnd(8) +
        'DY(%)'.padEnd(9) +
        'CapRate'.padEnd(8) +
        'Vacancy'.padEnd(9) +
        'Score'.padEnd(7) +
        'Liquidity'
    );
    console.log('-'.repeat(115));

    if (fiis.length > 0) {
        fiis.slice(0, 15).forEach(f => {
            let typeDisplay = f.type || 'N/A';
            console.log(
                f.ticker.padEnd(8) +
                typeDisplay.padEnd(10) +
                f.price.toFixed(2).padEnd(9) +
                f.p_vp.toFixed(2).padEnd(8) +
                (f.dy + '%').padEnd(9) +
                (f.cap_rate ? f.cap_rate.toFixed(1) + '%' : '-').padEnd(8) +
                (f.vacancy + '%').padEnd(9) +
                (f.score + '/10').padEnd(7) +
                f.liquidity.toLocaleString('pt-BR')
            );
        });
        console.log(`\nTotal FIIs found: ${fiis.length}`);
    } else {
        console.log('No FIIs found matching criteria.');
    }
    console.log('\n');

    // --- ETF DISPLAY ---
    console.log('--- 📊 POPULAR ETFs ---');
    console.log('-'.repeat(80));
    etfs.forEach(e => {
        console.log(`${e.ticker.padEnd(8)} | ${e.name} (${e.type})`);
    });
    console.log('\n');
    console.log('================================================================================');
}

main();
