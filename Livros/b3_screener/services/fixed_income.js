
const cheerio = require('cheerio');
const { getSelicRate } = require('./economy');

async function getTesouroDirect() {
    try {
        console.log('Fetching Tesouro Direto data...');
        const response = await fetch('https://investidor10.com.br/tesouro-direto/', {
            headers: { 'User-Agent': 'Mozilla/5.0' }
        });
        const html = await response.text();
        const $ = cheerio.load(html);

        console.log('HTML Length:', html.length);
        const rows = $('table tr');
        console.log('Rows found:', rows.length);

        const bonds = [];

        // Investidor10 usually has a table with class or just generic tables. 
        // We will iterate all rows and look for typical Tesouro names.
        rows.each((i, el) => {
            const cols = $(el).find('td');
            if (cols.length === 0) return;

            if (i < 5) { // Log first 5 rows
                console.log(`Row ${i}:`, $(el).text().replace(/\s+/g, ' ').trim());
            }

            // Standard Investidor10 table: 
            // Col 0: Name (Tesouro Selic...)
            // Col 1: Rentabilidade
            // Col 2: Inv. Minimo
            // Col 3: Preço
            // Col 4: Vencimento

            // Adjusted Logic based on Debug:
            // Sometimes Col 0 is a rank (number).
            let name = $(cols[0]).text().trim();
            let rate = $(cols[1]).text().trim();
            let minInvest = $(cols[2]).text().trim();
            let price = $(cols[3]).text().trim();
            let maturity = $(cols[4]).text().trim();

            // If name is just a number, shift columns
            if (/^\d+$/.test(name) || name.length < 3) {
                name = $(cols[1]).text().trim();
                rate = $(cols[2]).text().trim();
                minInvest = $(cols[3]).text().trim();
                price = $(cols[4]).text().trim();
                maturity = $(cols[5]).text().trim();
            }

            if (name.includes('Tesouro')) {
                bonds.push({ name, rate, minInvest, price, maturity });
            }
        });

        return bonds;

    } catch (error) {
        console.error('Error fetching Tesouro Direto:', error.message);
        return [];
    }
}

async function getPrivateBenchmarks(selicParam = null) {
    try {
        const selic = selicParam || await getSelicRate(); // e.g. 15.0
        const cdi = selic - 0.10; // CDI is usually Selic - 0.10

        // Poupança Rule:
        // If Selic > 8.5% -> 0.5% a.m. + TR (~6.17% a.a. + TR)
        // If Selic <= 8.5% -> 70% Selic + TR
        let poupanca = 0;
        if (selic > 8.5) {
            poupanca = 6.17; // Base annual without TR
        } else {
            poupanca = selic * 0.70;
        }

        return [
            { name: 'CDB 100% CDI', rate: `${cdi.toFixed(2)}%`, type: 'Pós-fixado' },
            { name: 'LCI/LCA 90% CDI', rate: `${(cdi * 0.90).toFixed(2)}%`, type: 'Isento IR' },
            { name: 'Poupança (Est.)', rate: `${poupanca.toFixed(2)}% + TR`, type: 'Isento IR' },
            { name: 'CDB Pré-fixado (Est.)', rate: `${(selic + 1.5).toFixed(2)}%`, type: 'Prefixado' } // Estimate
        ];

    } catch (error) {
        console.error('Error calculating Private Benchmarks:', error.message);
        return [];
    }
}

module.exports = { getTesouroDirect, getPrivateBenchmarks };
