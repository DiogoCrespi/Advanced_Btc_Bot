const axios = require('axios');
const cheerio = require('cheerio');

async function getTickersFromPage(url) {
    try {
        const headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://investidor10.com.br/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        };
        console.log(`Fetching ${url}...`);
        const response = await axios.get(url, { headers });
        const $ = cheerio.load(response.data);

        const tickers = [];
        // Try to find tickers in the list/table
        // Often in cards .actions .ticker or table rows
        // Strategy 1: Look for links like /fiagros/TICKER/
        $('a[href*="/fiagros/"], a[href*="/fi-infra/"]').each((i, el) => {
            const href = $(el).attr('href');
            const match = href.match(/\/(fiagros|fi-infra)\/([a-zA-Z0-9]+)\/?$/);
            if (match && match[2]) {
                tickers.push(match[2].toUpperCase());
            }
        });

        // Strategy 2: Look for specific cards
        $('.actions .ticker').each((i, el) => {
            tickers.push($(el).text().trim().toUpperCase());
        });

        return [...new Set(tickers)]; // Unique
    } catch (err) {
        console.error(`Error fetching ${url}:`, err.message);
        return [];
    }
}


async function getTickersFromFundsExplorer() {
    try {
        const url = 'https://www.fundsexplorer.com.br/ranking';
        const headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        };
        console.log(`Fetching ${url}...`);
        const response = await axios.get(url, { headers });
        const $ = cheerio.load(response.data);

        const tickers = [];
        // Funds Explorer usually has a table with tickers
        // Look for cells with ticker links or data-index
        $('#table-ranking tbody tr').each((i, el) => {
            const ticker = $(el).find('td').eq(0).text().trim().toUpperCase();
            if (ticker) tickers.push(ticker);
        });

        // Also check if they have specific infra/fiagro pages
        // But scraping the main ranking might give everything, then we filter?
        // Actually, FundsExplorer might list everything together or separate.

        return [...new Set(tickers)];
    } catch (err) {
        console.error(`Error fetching FundsExplorer:`, err.message);
        return [];
    }
}


async function getTickersFromClubeFII(type = 'fi-infra') {
    try {
        // ClubeFII often has /fi-infra, /fiagro
        const url = `https://www.clubefii.com.br/${type}`;
        const headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.google.com/'
        };
        console.log(`Fetching ${url}...`);
        const response = await axios.get(url, { headers });
        const $ = cheerio.load(response.data);

        const tickers = [];
        // Inspecting ClubeFII usually they have ticker links like /fi-infra/BDIF11
        $('a[href*="/' + type + '/"]').each((i, el) => {
            const href = $(el).attr('href');
            // href might be /fi-infra/BDIF11 or full url
            const parts = href.split('/');
            const ticker = parts[parts.length - 1]; // Last part usually ticker?
            // Verify if it looks like a ticker (4 letters + 11/12)
            if (ticker && /^[A-Z]{4}1[0-9]$/.test(ticker.toUpperCase())) {
                tickers.push(ticker.toUpperCase());
            }
        });

        return [...new Set(tickers)];
    } catch (err) {
        console.error(`Error fetching ClubeFII ${type}:`, err.message);
        return [];
    }
}


async function getTickersFromSuno() {
    try {
        // Suno Research Fiagros
        const url = 'https://www.suno.com.br/fiagros/';
        const headers = { 'User-Agent': 'Mozilla/5.0' };
        console.log(`Fetching ${url}...`);
        const response = await axios.get(url, { headers });
        const $ = cheerio.load(response.data);

        const tickers = [];
        $('.ticker').each((i, el) => {
            tickers.push($(el).text().trim().toUpperCase());
        });

        // Also try to find links
        $('a[href*="/fiagros/"]').each((i, el) => {
            const txt = $(el).text().trim().toUpperCase();
            if (/^[A-Z]{4}11$/.test(txt)) tickers.push(txt);
        });

        return [...new Set(tickers)];
    } catch (err) {
        console.error(`Error fetching Suno:`, err.message);
        return [];
    }
}


async function getTickersFromMaisRetorno(type = 'fiagro') {
    try {
        // maisretorno.com/lista-de-fiagro or similar? 
        // actually google says https://maisretorno.com/fii/fiagro
        const url = `https://maisretorno.com/fii/${type}`; // or similar path
        const headers = { 'User-Agent': 'Mozilla/5.0' };
        console.log(`Fetching ${url}...`);
        const response = await axios.get(url, { headers });
        const $ = cheerio.load(response.data);

        const tickers = [];
        // MaisRetorno usually puts tickers in valid links
        $('a[href*="/fii/"]').each((i, el) => {
            const txt = $(el).text().trim().toUpperCase();
            if (/^[A-Z]{4}11$/.test(txt)) tickers.push(txt);
        });

        return [...new Set(tickers)];
    } catch (err) {
        console.error(`Error fetching MaisRetorno:`, err.message);
        return [];
    }
}


async function getTickersFromB3() {
    try {
        // B3 often uses APIs that need base64 params, might be hard.
        // But let's try a direct search URL if possible or a known endpoint.
        // https://sistemaswebb3-listados.b3.com.br/fundsPage/7
        // Let's try to fetch a very simple public list if one exists.
        // Actually, let's try "ADVFN" which is usually old school and permissive.
        const url = 'https://br.advfn.com/bolsa-de-valores/bovespa/fiagros';
        const headers = { 'User-Agent': 'Mozilla/5.0' };
        console.log(`Fetching ${url}...`);
        const response = await axios.get(url, { headers });
        const $ = cheerio.load(response.data);

        const tickers = [];
        // ADVFN usually has a table
        $('a').each((i, el) => {
            const txt = $(el).text().trim().toUpperCase();
            if (/^[A-Z]{4}11$/.test(txt)) tickers.push(txt);
        });

        return [...new Set(tickers)];
    } catch (err) {
        console.error(`Error fetching ADVFN:`, err.message);
        return [];
    }
}


async function getTickersFromFiisComBr() {
    try {
        // https://fiis.com.br/lista-de-fiagros/
        const url = 'https://fiis.com.br/lista-de-fiagros/';
        const headers = { 'User-Agent': 'Mozilla/5.0' };
        console.log(`Fetching ${url}...`);
        const response = await axios.get(url, { headers });
        const $ = cheerio.load(response.data);

        const tickers = [];
        // Look for typical ticker pattern in links or text
        $('a').each((i, el) => {
            const txt = $(el).text().trim().toUpperCase();
            if (/^[A-Z]{4}11$/.test(txt)) tickers.push(txt);
        });

        return [...new Set(tickers)];
    } catch (err) {
        console.error(`Error fetching fiis.com.br:`, err.message);
        return [];
    }
}


async function getTickersFromInvestidor10Search() {
    try {
        // https://investidor10.com.br/api/busca/tickers/
        const urlBase = 'https://investidor10.com.br/api/busca/tickers/';
        const headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://investidor10.com.br/',
            'X-Requested-With': 'XMLHttpRequest'
        };

        const letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");
        let allTickers = [];

        for (const char of letters) {
            console.log(`Searching for "${char}"...`);
            try {
                // Post request with "term"
                // Actually inspection shows it's usually GET ?term=A or similar, or POST with form data.
                // Let's try GET first: /api/busca/tickers/?term=A
                const response = await axios.get(`${urlBase}?term=${char}`, { headers });
                const data = response.data; // Expecting array of objects { id, label, value, type }

                if (Array.isArray(data)) {
                    data.forEach(item => {
                        // Filter for FII types if possible. Investidor10 usually puts type in url or separate field
                        // item.url might be /fiis/TICKER/ or /fi-infra/TICKER/
                        if (item.url && (item.url.includes('/fi-infra/') || item.url.includes('/fiagros/'))) {
                            const match = item.url.match(/\/(fiagros|fi-infra)\/([a-zA-Z0-9]+)\/?/);
                            if (match && match[2]) allTickers.push(match[2].toUpperCase());
                        }
                    });
                }
            } catch (e) {
                console.warn(`Failed search for ${char}: ${e.message}`);
            }
            // Be nice
            await new Promise(r => setTimeout(r, 500));
        }

        return [...new Set(allTickers)];
    } catch (err) {
        console.error(`Error fetching Investidor10 Search:`, err.message);
        return [];
    }
}


async function probeFundamentusForTickers() {
    // Fundamentus doesn't list them in the main table, but maybe they exist if probed directly?
    // We can't bruteforce all AAAC11 combinations.
    // The "Method that wasn't mocked" implies there was a source.
    // Maybe we just hardcode the list but fetch data dynamically (which we are doing).
    // The user complains "Infra not listed".
    // If the user means the OLD method, maybe it was using a different provider.

    // Let's try to fetch a specific INFRA like BDIF11 from Fundamentus details page to see if it even exists there.
    try {
        const url = 'https://www.fundamentus.com.br/detalhes.php?papel=BDIF11';
        const headers = { 'User-Agent': 'Mozilla/5.0' };
        console.log(`Fetching ${url}...`);
        const response = await axios.get(url, { headers });

        if (response.data.includes('Papel N&atilde;o Encontrado') || response.data.includes('Nenhum papel encontrado')) {
            console.log('BDIF11 not found on Fundamentus.');
        } else {
            console.log('BDIF11 FOUND on Fundamentus!');
            // If found, we could potentialy use Fundamentus if we knew the list.
        }

    } catch (err) {
        console.error(`Error fetching Fundamentus probe:`, err.message);
    }
}


async function run() {
    console.log('--- STARTING DYNAMIC FETCH PROBES (WITH WARP EXPECTED) ---');

    // 1. Investidor10 Ranking Pages
    const i10Fiagro = await getTickersFromPage('https://investidor10.com.br/fiagros/');
    console.log(`[Investidor10] Found ${i10Fiagro.length} Fiagros.`);

    const i10Infra = await getTickersFromPage('https://investidor10.com.br/fi-infra/');
    console.log(`[Investidor10] Found ${i10Infra.length} Infras.`);

    // 2. FundsExplorer
    const feTickers = await getTickersFromFundsExplorer();
    console.log(`[FundsExplorer] Found ${feTickers.length} assets.`);

    // 3. ClubeFII
    const cfiiInfra = await getTickersFromClubeFII('fi-infra');
    console.log(`[ClubeFII] Found ${cfiiInfra.length} Infras.`);

    // 4. Suno
    const suno = await getTickersFromSuno();
    console.log(`[Suno] Found ${suno.length} Fiagros.`);

    // 5. MaisRetorno
    const mr = await getTickersFromMaisRetorno('fiagro');
    console.log(`[MaisRetorno] Found ${mr.length} Fiagros.`);

    // 6. Investidor10 Search API (Letter A probe)
    // const i10Search = await getTickersFromInvestidor10Search(); // Too long, maybe just probe 'A'

    // 7. Fundamentus Probe
    await probeFundamentusForTickers();

    console.log('--- END PROBES ---');
}

run();
