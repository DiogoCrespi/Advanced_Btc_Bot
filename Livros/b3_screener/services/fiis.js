const cheerio = require('cheerio');
const { getFiiMetadata } = require('./investidor10');
const { getSelicRate } = require('./economy');
const { NEVER_INFRA, KNOWN_FIAGROS, KNOWN_INFRAS } = require('./config/fii_lists');

const FII_URL = 'https://www.fundamentus.com.br/fii_resultado.php';

/**
 * Fetches and processes FII data.
 * @param {Object} externalMetadata - Optional metadata from external sources (mapping ticker -> meta)
 * @param {Array} baseList - Optional list of raw FII objects to process instead of fetching from Fundamentus
 * @param {number} selicParam - Optional Selic rate
 */
async function getBestFIIs(externalMetadata = {}, baseList = null, selicParam = null) {
    try {
        let fiis = [];

        if (baseList && Array.isArray(baseList)) {
            fiis = baseList;
        } else {
            const response = await fetch(FII_URL, {
                headers: { 'User-Agent': 'Mozilla/5.0' }
            });

            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const html = await response.text();
            const $ = cheerio.load(html);

            $('#tabelaResultado tbody tr').each((i, el) => {
                const tds = $(el).find('td');
                const parseNumber = (text) => {
                    if (!text) return 0;
                    return parseFloat(text.replace(/\./g, '').replace(',', '.').replace('%', ''));
                };

                fiis.push({
                    ticker: $(tds[0]).text().trim(),
                    segment: $(tds[1]).text().trim(),
                    price: parseNumber($(tds[2]).text().trim()),
                    ffo_yield: parseNumber($(tds[3]).text().trim()),
                    dy: parseNumber($(tds[4]).text().trim()),
                    p_vp: parseNumber($(tds[5]).text().trim()),
                    market_cap: parseNumber($(tds[6]).text().trim()),
                    liquidity: parseNumber($(tds[7]).text().trim()),
                    num_properties: parseNumber($(tds[8]).text().trim()),
                    cap_rate: parseNumber($(tds[11]).text().trim()),
                    vacancy: parseNumber($(tds[12]).text().trim())
                });
            });


            // Dynamic discovery is now handled primarily by export_data.js calling getFIInfra()
        }

        let selic = selicParam;
        if (!selic) {
            const fetchedSelic = await getSelicRate();
            if (fetchedSelic !== null && !isNaN(fetchedSelic)) {
                selic = fetchedSelic;
            } else {
                console.warn('⚠️  Could not fetch Selic for FIIs, using default 12.75%.');
                selic = 12.75;
            }
        }

        const MIN_PAPER_DY = selic - 1.5;
        const MIN_BRICK_DY = 6.0;
        const GOOD_CAP_RATE = 8.0;
        const MAX_PAPER_PVP = 1.05;

        return fiis
            .filter(f => f.liquidity > 200000)
            .map(f => {
                const meta = externalMetadata[f.ticker] || {};

                // 1. CLASSIFICATION LOGIC
                // Normalization helper (removes accents and toLowerCase)
                const norm = (s) => s ? s.normalize('NFD').replace(/[\u0300-\u036f]/g, "").toLowerCase() : "";

                const exType = norm(meta.type);
                const exMandate = norm(meta.mandate);
                const exSegment = norm(meta.segment);
                const segmentNorm = norm(f.segment);
                let type = f.type || 'OUTROS';

                // Defensive check: Well-known non-infra tickers should never be tagged as INFRA
                if (NEVER_INFRA.includes(f.ticker)) {
                    if (type === 'OUTROS' || type === 'INFRA') type = 'MULTI';
                }

                if (type === 'OUTROS') {
                    // PRIORITY 1: INFRA & AGRO (Specific tax-advantaged categories)
                    if (exType.includes('infra') || exSegment.includes('infra') || exMandate.includes('infra')) {
                        type = 'INFRA';
                    } else if (exType.includes('fiagro') || exSegment.includes('fiagro') || exMandate.includes('agro') || exMandate.includes('rural')) {
                        type = 'AGRO';
                    }
                    // PRIORITY 2: MISTO / MULTI (Hybrid nature)
                    else if (exType.includes('misto') || exType.includes('mista') ||
                        exType.includes('hibrido') || exMandate.includes('hibrido') ||
                        exSegment.includes('hibrido') || exMandate.includes('misto') ||
                        exType.includes('multimercado') || exType.includes('fundos de fundos')) {
                        type = 'MULTI';
                    }
                    // PRIORITY 3: Explicit PAPEL & TIJOLO (From Investidor10 Type)
                    else if (exType.includes('papel') || exMandate.includes('titulos')) {
                        type = 'PAPEL';
                    } else if (exType.includes('tijolo') || exMandate.includes('renda')) {
                        type = 'TIJOLO';
                    }
                    // PRIORITY 4: Fallbacks based on Segment (if Type was generic or missing)
                    else if (exSegment.includes('recebiveis')) {
                        type = 'PAPEL';
                    } else if (exSegment.includes('imoveis')) {
                        type = 'TIJOLO';
                    } else {
                        // FALLBACK: Fundamentus Segment Analysis
                        const isTijolo = segmentNorm.includes('logistica') ||
                            segmentNorm.includes('shopping') ||
                            segmentNorm.includes('lajes') ||
                            segmentNorm.includes('escritorio') ||
                            segmentNorm.includes('hospital') ||
                            segmentNorm.includes('hotel') ||
                            segmentNorm.includes('residencial') ||
                            segmentNorm.includes('varejo');

                        const isAgro = segmentNorm.includes('agro') || segmentNorm.includes('fiagro') || segmentNorm.includes('rural');
                        const isInfra = segmentNorm.includes('infra') || segmentNorm.includes('energia') || segmentNorm.includes('saneamento');
                        const isMulti = segmentNorm.includes('multicategoria') || segmentNorm.includes('hibrido') || segmentNorm.includes('fundos') || segmentNorm.includes('mista');

                        if (isTijolo) type = 'TIJOLO';
                        else if (isAgro) type = 'AGRO';
                        else if (isInfra) type = 'INFRA';
                        else if (segmentNorm.includes('titulos') || segmentNorm.includes('recebiveis')) type = 'PAPEL';
                        else if (isMulti) type = 'MULTI';
                    }
                }

                // Explicitly check for known Fiagros/Infras if still "OUTROS"
                if (type === 'OUTROS' || type === 'MULTI') {
                    if (KNOWN_FIAGROS.includes(f.ticker)) type = 'AGRO';
                    if (KNOWN_INFRAS.includes(f.ticker)) type = 'INFRA';
                }

                // If the segment name suggests it, force it (unless it's a known non-infra)
                if (!NEVER_INFRA.includes(f.ticker)) {
                    if (segmentNorm.includes('fiagro')) type = 'AGRO';
                    if (segmentNorm.includes('infra')) type = 'INFRA';
                }

                // --- 2. STRATEGY RE-CALCULATION & SCORING SYSTEM (NEW LOGIC) ---
                let score = 0;
                const strategies = [];
                let category = 'STANDARD';

                const isAgro = type === 'AGRO';
                const isInfra = type === 'INFRA';
                const isMulti = type === 'MULTI';
                const isTijolo = type === 'TIJOLO';
                const isPapel = type === 'PAPEL';

                // --- 1. VALUATION (P/VP) ---
                // Tijolo: Desconto é bom, mas desconto DEMAIS (0.60) é suspeito.
                if (isTijolo) {
                    if (f.p_vp >= 0.70 && f.p_vp <= 0.95) score += 2; // Bom ponto de entrada
                    else if (f.p_vp > 0.95 && f.p_vp <= 1.05) score += 1; // Preço Justo
                    // Sem pontuação para P/VP < 0.70 (Risco de imóvel ruim)
                } else {
                    // Papel: Preço justo é rei. Desconto é risco.
                    if (f.p_vp >= 0.90 && f.p_vp <= 1.02) score += 2;
                    else if (f.p_vp < 0.85) {
                        score -= 3; // PENALIDADE GRAVE: Risco de Calote
                        strategies.push('DISTRESSED_RISK');
                    }
                }

                // --- 2. YIELD (Dividendo Racional) ---
                // O GRUL11 ganhou aqui antes. Agora vamos limitar o impacto.
                const rationalYield = Math.min(f.dy, 14); // Teto de 14% para cálculo
                if (rationalYield > 10) score += 2;
                else if (rationalYield > 8) score += 1;
                else if (isTijolo && rationalYield >= MIN_BRICK_DY) score += 0.5; // Small bump for meeting min brick yield

                // --- 3. LIQUIDEZ (A Correção do "Caso GRUL11") ---
                // Aqui é onde matamos o problema.
                if (f.liquidity > 4000000) score += 3;      // Liquidez de "Blue Chip"
                else if (f.liquidity > 1500000) score += 2; // Liquidez Saudável
                else if (f.liquidity > 800000) score += 1;  // Liquidez Aceitável
                else if (f.liquidity < 400000) score -= 2;  // PENALIDADE: Porta de saída estreita (Caso GRUL11)

                // --- 4. TAMANHO/ROBUSTEZ (O Proxy de Concentração) ---
                // Fundos grandes (>1bi) raramente são mono-imóvel.
                const patrimonio = f.market_cap || 0;

                if (patrimonio > 2000000000) score += 2;      // Gigante (Muito Seguro)
                else if (patrimonio > 1000000000) score += 1; // Grande (Seguro)
                else if (patrimonio < 400000000) score -= 1;  // Pequeno (Risco de ser Monativo)

                // --- 5. VACÂNCIA (Tijolo) ---
                if (isTijolo) {
                    if (f.vacancy < 3) score += 1;
                    else if (f.vacancy > 15) score -= 2; // Prédio vazio é custo
                }

                // --- CATEGORIZAÇÃO ---
                // Para ser STAR, tem que ter LIQUIDEZ. Não basta yield alto.
                if (score >= 8 && f.liquidity > 1000000 && patrimonio > 1000000000) {
                    category = 'STAR'; // O melhor dos mundos (BBIG11 entraria aqui)
                } else if (score >= 6) {
                    category = 'OPPORTUNITY'; // GRUL11 cairia para cá ou abaixo
                } else {
                    category = 'STANDARD';
                }

                // Estratégias Específicas
                if (isTijolo && f.p_vp < 0.90 && patrimonio > 1000000000) strategies.push('TIJOLO_VALUE');
                if (isPapel && f.dy > 11 && f.p_vp >= 0.95) strategies.push('PAPEL_CARRY');


                score = Math.max(0, Math.min(10, score));

                // 4. MAGIC NUMBER
                const magicNumber = f.dy > 0 ? Math.ceil(1200 / f.dy) : 9999;
                const magicCost = magicNumber * f.price;

                return {
                    ...f, strategies, type, score, selic, magicNumber, magicCost, category,
                    last_dividend: meta.last_dividend || null,
                    external_segment: meta.segment || null,
                    data_com: meta.data_com || null,
                    data_pagamento: meta.data_pagamento || null
                };
            })
            // Filter: Allow more items in the re-classification stage
            .filter(f => f.strategies.length > 0 || f.score >= 5.5)
            .sort((a, b) => b.score - a.score || b.dy - a.dy);

    } catch (error) {
        console.error('Error fetching/parsing FIIs:', error.message);
        return [];
    }
}

module.exports = { getBestFIIs };
