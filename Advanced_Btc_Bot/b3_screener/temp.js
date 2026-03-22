
        function escapeHTML(str) {
            if (typeof str !== 'string') return str;
            return str
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        // --- Search Functionality ---
        let searchResults = [];
        let currentMatchIndex = 0;

        function toggleSearch() {
            const container = document.getElementById('searchContainer');
            container.classList.toggle('show');
            if (container.classList.contains('show')) {
                document.getElementById('searchInput').focus();
            }
        }

        document.getElementById('searchInput').addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase().trim();

            // Remove previous highlights
            document.querySelectorAll('.card-highlight').forEach(el => el.classList.remove('card-highlight'));

            if (term.length < 2) {
                searchResults = [];
                updateSearchUI();
                return;
            }

            // Find all searchable items across all tabs
            // We query the DOM directly to respect what's actually rendered
            const allItems = Array.from(document.querySelectorAll('[data-search-term]'));

            searchResults = allItems.filter(item => {
                // Exclude items in the hidden FIIs tab
                if (item.closest('#content-fiis')) return false;

                const searchData = item.dataset.searchTerm;
                return searchData.includes(term);
            });

            currentMatchIndex = 0;
            updateSearchUI();
            if (searchResults.length > 0) {
                highlightCurrentMatch();
            }
        });

        function updateSearchUI() {
            const countEl = document.getElementById('searchCount');
            if (searchResults.length === 0) {
                countEl.textContent = '0/0';
            } else {
                countEl.textContent = `${currentMatchIndex + 1}/${searchResults.length}`;
            }
        }

        function navigateSearch(direction) {
            if (searchResults.length === 0) return;

            currentMatchIndex += direction;
            if (currentMatchIndex >= searchResults.length) currentMatchIndex = 0;
            if (currentMatchIndex < 0) currentMatchIndex = searchResults.length - 1;

            updateSearchUI();
            highlightCurrentMatch();
        }

        function highlightCurrentMatch() {
            // Remove previous highlights
            document.querySelectorAll('.card-highlight').forEach(el => el.classList.remove('card-highlight'));

            const element = searchResults[currentMatchIndex];
            if (!element) return;

            // 1. Ensure Tab is visible
            const parentList = element.closest('.list-container');
            if (parentList) {
                const listId = parentList.id;
                // id is like "content-stocks", "content-fiis"
                // showTab expects "stocks", "fiis"
                const tabName = listId.replace('content-', '');
                showTab(tabName);
            }

            // 2. Ensure Element is visible (if hidden by filters)
            if (window.getComputedStyle(element).display === 'none') {
                element.style.display = 'block';
            }

            // 3. Scroll and Highlight
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            element.classList.add('card-highlight');
        }

        // Theme Logic
        const themeBtn = document.getElementById('themeBtn');
        const savedTheme = localStorage.getItem('theme');

        if (savedTheme === 'light') {
            document.body.classList.add('light-mode');
            themeBtn.textContent = '🌙';
        }

        function toggleTheme() {
            document.body.classList.toggle('light-mode');
            const isLight = document.body.classList.contains('light-mode');
            themeBtn.textContent = isLight ? '🌙' : '☀️';
            localStorage.setItem('theme', isLight ? 'light' : 'dark');
        }

        // CSV Download Logic
        function toggleDownloadMenu() {
            document.getElementById('downloadOptions').classList.toggle('show');
        }

        // Close menu when clicking outside
        window.addEventListener('click', (e) => {
            if (!document.getElementById('downloadMenu').contains(e.target)) {
                document.getElementById('downloadOptions').classList.remove('show');
            }
        });

        function downloadCSV(type) {
            if (!window.INVEST_DATA) return;
            let data;
            if (type === 'stocks') data = window.INVEST_DATA.stocks;
            else if (type === 'fiis') data = window.INVEST_DATA.fiis;
            else if (type === 'etfs') data = window.INVEST_DATA.etfs;

            if (!data || data.length === 0) return;

            // Define priority columns for better organization
            const priorityKeys = type === 'stocks'
                ? ['ticker', 'category', 'cotacao', 'dividend_yield', 'p_vp', 'score', 'upside', 'pl', 'roe', 'liq_2meses', 'graham_price', 'bazin_price', 'data_com', 'data_pagamento']
                : type === 'fiis'
                    ? ['ticker', 'type', 'price', 'dy', 'p_vp', 'score', 'liquidity', 'vacancy', 'cap_rate', 'magicNumber', 'magicCost', 'last_dividend', 'segment', 'data_com', 'data_pagamento']
                    : ['ticker', 'price', 'dy', 'liquidity', 'high_52w', 'low_52w', 'variation_12m'];

            const allKeys = new Set(priorityKeys);
            data.forEach(item => {
                Object.keys(item).forEach(key => {
                    if (typeof item[key] !== 'object' || Array.isArray(item[key])) {
                        allKeys.add(key);
                    }
                });
            });
            const headers = Array.from(allKeys).filter(k => data.some(item => k in item));

            const csvRows = [];
            csvRows.push(headers.join(','));

            for (const row of data) {
                const values = headers.map(header => {
                    let val = row[header];
                    if (val === undefined || val === null) val = '';
                    if (Array.isArray(val)) val = val.join('; ');

                    const str = String(val);
                    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                        return `"${str.replace(/"/g, '""')}"`;
                    }
                    return str;
                });
                csvRows.push(values.join(','));
            }

            const csvString = csvRows.join('\n');
            const blob = new Blob([csvString], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);

            link.setAttribute('href', url);
            link.setAttribute('download', `${type}_${new Date().toISOString().split('T')[0]}.csv`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            document.getElementById('downloadOptions').classList.remove('show');
        }

        document.addEventListener('DOMContentLoaded', () => {
            if (!window.INVEST_DATA) {
                document.querySelector('.list-container').innerHTML = '<p style="text-align:center">Nenhum dado encontrado (.js). Rode o exportador!</p>';
                return;
            }

            const data = window.INVEST_DATA;

            // Header
            document.getElementById('lastUpdate').textContent = `Atualizado em: ${data.updatedAt}`;
            document.getElementById('dollarVal').textContent = data.economy.dollar ? `R$ ${data.economy.dollar.toFixed(2)}` : '---';

            const selic = data.economy.selic;
            const selicEl = document.getElementById('selicVal');
            selicEl.textContent = selic ? `${selic.toFixed(2)}%` : '---';

            // Show dynamic DY threshold notice
            const minDY = selic > 10 ? 4 : 6;
            const selicContext = document.createElement('div');
            selicContext.className = 'last-update';
            selicContext.style.textAlign = 'center';
            selicContext.style.marginTop = '-10px';
            selicContext.style.marginBottom = '15px';
            selicContext.innerHTML = `Filtro DY Atual: <strong style="color:var(--success)">>${minDY}%</strong> (Selic ${selic > 10 ? 'Alta' : 'Normal'})`;
            document.querySelector('.dashboard').after(selicContext);



            // Render Stocks
            const stockContainer = document.getElementById('content-stocks');

            const getTrendArrow = (value, type) => {
                if (value === undefined || value === null) return '';
                const up = '<span class="arrow-up">↑</span>';
                const down = '<span class="arrow-down">↓</span>';
                switch (type) {
                    case 'pl': return value > 0 ? up : down;
                    case 'pvp': return value <= 1.2 ? up : down;
                    case 'roe': return value > 10 ? up : down;
                    case 'liq': return value > 200000 ? up : down;
                    case 'div_patrim': return value < 0.5 ? up : down;
                    case 'cresc': return value > 0 ? up : down;
                    case 'vacancy': return value < 10 ? up : down;
                    case 'liq-fii': return value > 50000 ? up : down;
                    case 'mkt-cap': return value > 500000000 ? up : down;
                    default: return '';
                }
            };

            const stars = data.stocks.filter(s => s.category === 'STAR');
            const opportunities = data.stocks.filter(s => s.category === 'OPPORTUNITY');

            // 1. STARS SECTION
            if (stars.length > 0) {
                const starHeader = document.createElement('h2');
                starHeader.innerHTML = '⭐ TOP STARS <span style="font-size:0.8rem; font-weight:normal; color:var(--text-muted)">(Ouro: Qualidade + Crescimento + Renda)</span>';
                starHeader.style.width = '100%';
                starHeader.style.margin = '1rem 0 1rem 0';
                starHeader.style.color = '#FFD700'; // Gold
                starHeader.style.gridColumn = '1 / -1'; // Spans full width

                stockContainer.appendChild(starHeader);

                stars.forEach(stock => renderStockCard(stock, stockContainer, true));
            }

            // 2. OPPORTUNITIES SECTION
            if (opportunities.length > 0) {
                const oppHeader = document.createElement('h2');
                oppHeader.innerHTML = '📈 OPORTUNIDADES <span style="font-size:0.8rem; font-weight:normal; color:var(--text-muted)">(Lucrativas & Valor Descontado)</span>';

                oppHeader.style.width = '100%';
                oppHeader.style.margin = '2rem 0 1rem 0';
                oppHeader.style.color = 'var(--text-color)';
                oppHeader.style.gridColumn = '1 / -1'; // Spans full width

                stockContainer.appendChild(oppHeader);

                // --- FILTER UI ---
                const filterContainer = document.createElement('div');
                filterContainer.className = 'opp-filters';
                filterContainer.style.gridColumn = '1 / -1'; // Spans full width


                const strategies = [
                    { id: 'ALL', label: 'Ver Todas' },
                    { id: 'QUALITY', label: '💎 Quality' },
                    { id: 'DIVIDEND', label: '💰 Dividendos' },
                    { id: 'VALUE', label: '📉 Valor/Desconto' },
                    { id: 'GROWTH', label: '🚀 Crescimento' },
                    { id: 'MAGIC', label: '🪄 Magic Formula' },
                    { id: 'TURNAROUND', label: '🔄 Turnaround' },
                    { id: 'HIGH_VOLATILITY', label: '⚠️ Volatilidade' }

                ];

                strategies.forEach(s => {
                    const btn = document.createElement('button');
                    btn.textContent = s.label;
                    btn.className = 'filter-btn ' + (s.id === 'ALL' ? 'active' : '');
                    btn.dataset.id = s.id;
                    btn.onclick = () => filterOpportunities(s.id, btn);
                    filterContainer.appendChild(btn);
                });
                stockContainer.appendChild(filterContainer);
                // -----------------

                opportunities.forEach(stock => renderStockCard(stock, stockContainer, false));
            }

            // Filter Logic Function
            window.filterOpportunities = function (strategy, btn) {
                // Update buttons
                document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Filter cards
                const cards = document.querySelectorAll('.stock-card[data-type="opportunity"]');
                let visibleCount = 0;

                cards.forEach(card => {
                    const cardStrategies = (card.dataset.strategies || '').split(',');
                    if (strategy === 'ALL' || cardStrategies.includes(strategy)) {
                        card.style.display = 'block';
                        visibleCount++;
                    } else {
                        card.style.display = 'none';
                    }
                });
            };

            // FII Filter Logic
            window.filterFIIs = function (strategy, btn) {
                // Update buttons
                const container = btn.parentNode;
                container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Filter cards
                const cards = document.querySelectorAll('.stock-card.fii');

                cards.forEach(card => {
                    const cardType = card.dataset.type;
                    const cardStrategies = (card.dataset.strategies || '').split(',');

                    let show = false;
                    if (strategy === 'ALL') {
                        show = true;
                    } else if (strategy === 'SAFE_INCOME') {
                        show = cardStrategies.includes('SAFE_INCOME');
                    } else {
                        // Strategy works as TYPE matching now
                        show = (cardType === strategy);
                    }

                    card.style.display = show ? 'block' : 'none';
                });
            };

            function renderStockCard(stock, container, isStar) {
                const card = document.createElement('div');
                card.className = 'stock-card high-upside';
                card.dataset.searchTerm = `${escapeHTML(stock.ticker)} acao`.toLowerCase();

                // Add attributes for filtering
                if (!isStar) {
                    card.dataset.type = 'opportunity';
                    // stock.strategies is an array, join it for the attribute
                    card.dataset.strategies = stock.strategies ? escapeHTML(stock.strategies.join(',')) : '';
                }

                if (isStar) card.style.borderLeftColor = '#FFD700'; // Gold border for stars

                const badge = isStar
                    ? `<span class="badge" style="background:#FFD700; color:black">⭐ ${escapeHTML(String(stock.score))}/12</span>`
                    : `<span class="badge" style="background:var(--card-hover); color:var(--text-muted)">${escapeHTML(String(stock.score))}/12</span>`;

                const volBadge = (stock.strategies && stock.strategies.includes('HIGH_VOLATILITY'))
                    ? `<span class="badge" style="background:var(--danger); color:white" title="Dividend Yield > 16% (Risco de não recorrência)">⚠️ Volatilidade</span>`
                    : '';

                card.innerHTML = `
                <div class="card-main">
                    <div class="ticker-info">
                        <h3>
                            <img src="https://raw.githubusercontent.com/thefintz/icones-b3/main/icones/${escapeHTML(stock.ticker)}.png"
                                 class="stock-logo" 
                                 onerror="this.style.display='none'"
                                 alt="${escapeHTML(stock.ticker)}">
                            ${escapeHTML(stock.ticker)}
                            ${badge}
                            ${volBadge}
                        </h3>
                        <span style="font-size:0.8rem; color:var(--text-muted)">Graham: R$ ${escapeHTML(stock.graham_price.toFixed(2))} | Bazin: R$ ${escapeHTML(stock.bazin_price.toFixed(2))}</span>
                    </div>
                    <div class="metrics" style="display:flex; align-items:center; gap:12px;">
                        <div style="text-align:right">
                            <div class="price">R$ ${escapeHTML(stock.cotacao.toFixed(2))}</div>
                            <div style="display:flex; gap:4px; justify-content:flex-end; margin-top:4px;">
                                <span class="badge ${stock.dividend_yield > 8 ? 'price-badge' : ''}">DY ${escapeHTML(String(stock.dividend_yield))}%</span>
                                <span class="badge">P/VP ${escapeHTML(stock.p_vp?.toFixed(1) || 'N/A')}</span>
                            </div>
                        </div>
                        <div class="score-indicator ${isStar ? 'score-star' : (stock.score >= 8 ? 'score-good' : stock.score >= 6 ? 'score-warning' : 'score-danger')}">
                            ${escapeHTML(String(stock.score))}
                        </div>
                    </div>
                </div>
                <div class="card-details">
                    <div class="detail-grid">
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">P/L</span><span class="detail-value">${escapeHTML(stock.pl?.toFixed(2) || 'N/A')} ${getTrendArrow(stock.pl, 'pl')}</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">ROE</span><span class="detail-value">${escapeHTML(stock.roe?.toFixed(1) || 'N/A')}% ${getTrendArrow(stock.roe, 'roe')}</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Graham Price</span><span class="detail-value">R$ ${escapeHTML(stock.graham_price?.toFixed(2) || 'N/A')}</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Bazin Price</span><span class="detail-value">R$ ${escapeHTML(stock.bazin_price?.toFixed(2) || 'N/A')}</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Upside Graham</span><span class="detail-value" style="color:${stock.upside > 20 ? 'var(--success)' : ''}">+${escapeHTML(stock.upside.toFixed(0))}%</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">PSR</span><span class="detail-value">${escapeHTML(stock.psr?.toFixed(2) || 'N/A')}</span></div>
                        </div>
                    </div>

                    <div class="detail-row" style="flex-direction:row; justify-content:space-between; margin-bottom:8px;">
                        <span class="detail-label">Última Data Com:</span>
                        <span class="detail-value" style="color:var(--warning)">${stock.data_com || 'N/A'}</span>
                    </div>
                    <div class="detail-row" style="flex-direction:row; justify-content:space-between; margin-bottom:8px;">
                        <span class="detail-label">Último Pagamento:</span>
                        <span class="detail-value" style="color:var(--success)">${stock.data_pagamento || 'N/A'}</span>
                    </div>

                    <div class="detail-grid" style="grid-template-columns: 1fr 1fr 1fr; gap:8px;">
                        <div class="detail-box"><div class="detail-row"><span class="detail-label">PEG</span><span class="detail-value">${escapeHTML((stock.peg_ratio && stock.peg_ratio < 50) ? stock.peg_ratio.toFixed(2) : 'N/A')}</span></div></div>
                        <div class="detail-box"><div class="detail-row"><span class="detail-label">ROIC</span><span class="detail-value">${escapeHTML(stock.roic?.toFixed(1) || 'N/A')}%</span></div></div>
                        <div class="detail-box"><div class="detail-row"><span class="detail-label">Payout</span><span class="detail-value">${escapeHTML(stock.payout ? stock.payout.toFixed(0) + '%' : 'N/A')}</span></div></div>
                    </div>

                    <div id="chart-${escapeHTML(stock.ticker)}" class="chart-container"></div>
                    <a href="${getInvestidor10Url(stock)}" target="_blank" class="external-link-btn">
                        📊 Ver no Investidor 10
                    </a>
                </div>
            `;
                card.addEventListener('click', () => {
                    const isExpanded = card.classList.toggle('expanded');
                    card.querySelector('.card-details').classList.toggle('show');

                    if (isExpanded) {
                        const chartId = `chart-${stock.ticker}`;
                        const container = document.getElementById(chartId);
                        if (container && container.children.length === 0) {
                            new TradingView.MediumWidget({
                                "symbols": [[`${stock.ticker}`, `BMFBOVESPA:${stock.ticker}|1D`]],
                                "chartOnly": false,
                                "width": "100%",
                                "height": 300,
                                "locale": "br",
                                "colorTheme": "dark",
                                "autosize": true,
                                "showVolume": false,
                                "hideDateRanges": false,
                                "scalePosition": "right",
                                "scaleMode": "Normal",
                                "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
                                "noTimeScale": false,
                                "valuesTracking": "1",
                                "changeMode": "price-and-percent",
                                "chartType": "area",
                                "adjustment": "dividends",
                                "container_id": chartId
                            });
                        }
                    }
                });
                container.appendChild(card);
            }

            // Render FIIs
            const fiiContainer = document.getElementById('content-fiis');

            // --- FII FILTER UI ---
            const fiiFilterContainer = document.createElement('div');
            fiiFilterContainer.className = 'opp-filters';
            fiiFilterContainer.style.marginTop = '1rem';
            fiiFilterContainer.style.gridColumn = '1 / -1'; // Spans full width in grid


            const fiiStrategies = [
                { id: 'ALL', label: 'Ver Todos' },
                { id: 'TIJOLO', label: '🧱 Tijolo' },
                { id: 'PAPEL', label: '📄 Papel' },
                { id: 'AGRO', label: '🌾 Fiagro/Agro' },
                { id: 'MULTI', label: '🔄 Multimercado' },
                { id: 'INFRA', label: '⚡ Infra' },
                { id: 'SAFE_INCOME', label: '🛡️ Renda Segura' }
            ];

            fiiStrategies.forEach(s => {
                const btn = document.createElement('button');
                btn.textContent = s.label;
                btn.className = 'filter-btn ' + (s.id === 'ALL' ? 'active' : '');
                btn.onclick = () => filterFIIs(s.id, btn);
                fiiFilterContainer.appendChild(btn);
            });
            fiiContainer.prepend(fiiFilterContainer); // Insert INSIDE list (top)

            // ---------------------

            // Group and Render FIIs by type
            const typesOrder = ['AGRO', 'INFRA', 'TIJOLO', 'PAPEL', 'MULTI', 'OUTROS'];
            const labels = {
                'AGRO': '🌾 Fiagro & Agronegócio',
                'INFRA': '⚡ Infraestrutura & Energia',
                'TIJOLO': '🧱 Tijolo (Ativos Reais)',
                'PAPEL': '📄 Papel (CRI/Recebíveis)',
                'MULTI': '🔄 Multimercado & FoF',
                'OUTROS': '📂 Outros Segmentos'
            };

            const colors = {
                'AGRO': '#fba94c',
                'INFRA': '#00d4ff',
                'TIJOLO': '#555',
                'PAPEL': '#aaa',
                'MULTI': '#8257e5',
                'OUTROS': '#333'
            };

            typesOrder.forEach(type => {
                const fiisOfType = data.fiis.filter(f => (f.type || 'OUTROS') === type);
                if (fiisOfType.length === 0) return;

                const header = document.createElement('h2');
                header.innerHTML = labels[type];
                header.className = 'group-header';
                header.style.gridColumn = '1 / -1';
                header.style.color = colors[type];
                header.style.marginTop = '2rem';
                header.dataset.type = type;
                fiiContainer.appendChild(header);

                fiisOfType.forEach(fii => {
                    const card = document.createElement('div');
                    card.className = 'stock-card fii';
                    card.dataset.searchTerm = `${fii.ticker} ${fii.segment} fii`.toLowerCase();
                    card.dataset.type = type;
                    card.dataset.strategies = fii.strategies ? fii.strategies.join(',') : '';

                    const scoreColor = fii.score >= 8 ? '#04d361' : (fii.score >= 6 ? '#fba94c' : '#f75a68');

                    let typeBadge = '';
                    if (fii.type === 'TIJOLO') typeBadge = `<span class="badge" style="background:${colors.TIJOLO}; color:white">🧱 TIJOLO</span>`;
                    else if (fii.type === 'PAPEL') typeBadge = `<span class="badge" style="background:${colors.PAPEL}; color:black">📄 PAPEL</span>`;
                    else if (fii.type === 'AGRO') typeBadge = `<span class="badge" style="background:${colors.AGRO}; color:black">🌾 AGRO</span>`;
                    else if (fii.type === 'INFRA') typeBadge = `<span class="badge" style="background:${colors.INFRA}; color:black">⚡ INFRA</span>`;
                    else if (fii.type === 'MULTI') typeBadge = `<span class="badge" style="background:${colors.MULTI}; color:white">🔄 MULTI</span>`;
                    else typeBadge = `<span class="badge" style="background:${colors.OUTROS}; color:#aaa">OUTROS</span>`;

                    card.innerHTML = `
                <div class="card-main">
                    <div class="ticker-info">
                        <h3>
                            <img src="https://raw.githubusercontent.com/thefintz/icones-b3/main/icones/${escapeHTML(fii.ticker)}.png"
                                 class="stock-logo" 
                                 onerror="this.style.display='none'"
                                 alt="${escapeHTML(fii.ticker)}">
                            ${escapeHTML(fii.ticker)}
                            ${typeBadge}
                        </h3>
                        <span style="font-size:0.8rem; color:var(--text-muted)">${escapeHTML(fii.segment)}</span>
                    </div>
                    <div class="metrics" style="display:flex; align-items:center; gap:12px;">
                        <div style="text-align:right">
                            <div class="price">R$ ${escapeHTML(fii.price.toFixed(2))}</div>
                            <div style="display:flex; gap:4px; justify-content:flex-end; margin-top:4px;">
                                <span class="badge ${fii.dy > 8 ? 'price-badge' : ''}">DY ${escapeHTML(String(fii.dy))}%</span>
                                <span class="badge">P/VP ${escapeHTML((fii.p_vp || fii.pvp || 0).toFixed(2))}</span>
                            </div>
                        </div>
                        <div class="score-indicator ${fii.score >= 8 ? 'score-good' : (fii.score >= 6 ? 'score-warning' : 'score-danger')}">
                            ${escapeHTML(String(fii.score))}
                        </div>
                    </div>
                </div>
                <div class="card-details">
                    <div class="detail-grid">
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">FFO Yield</span><span class="detail-value">${escapeHTML(String(fii.ffo_yield || 'N/A'))}% ${getTrendArrow(fii.ffo_yield, 'roe')}</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Cap Rate</span><span class="detail-value">${escapeHTML(String(fii.cap_rate || 'N/A'))}% ${getTrendArrow(fii.cap_rate, 'roe')}</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Vacância</span><span class="detail-value">${escapeHTML(String(fii.vacancy))}% ${getTrendArrow(fii.vacancy, 'vacancy')}</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Imóveis</span><span class="detail-value">${escapeHTML(String(fii.num_properties || 'N/A'))} ${getTrendArrow(fii.num_properties, 'cresc')}</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Liquidez Diária</span><span class="detail-value">R$ ${escapeHTML((fii.liquidity / 1000).toFixed(0))}k ${getTrendArrow(fii.liquidity, 'liq-fii')}</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">V. Mercado</span><span class="detail-value">R$ ${escapeHTML((fii.market_cap / 1000000).toFixed(0))}M ${getTrendArrow(fii.market_cap, 'mkt-cap')}</span></div>
                        </div>
                    </div>
                    
                    <div class="detail-row" style="flex-direction:row; justify-content:space-between; margin-bottom:8px;">
                        <span class="detail-label">Última Data Com:</span>
                        <span class="detail-value" style="color:var(--warning)">${fii.data_com || 'N/A'}</span>
                    </div>
                    <div class="detail-row" style="flex-direction:row; justify-content:space-between; margin-bottom:8px;">
                        <span class="detail-label">Último Pagamento:</span>
                        <span class="detail-value" style="color:var(--success)">${fii.data_pagamento || 'N/A'}</span>
                    </div>

                    <div id="chart-${escapeHTML(fii.ticker)}" class="chart-container"></div>
                    <a href="${getInvestidor10Url(fii)}" target="_blank" class="external-link-btn">
                        📊 Ver no Investidor 10
                    </a>
                </div>
            `;
                    card.addEventListener('click', () => {
                        const isExpanded = card.classList.toggle('expanded');
                        card.querySelector('.card-details').classList.toggle('show');

                        if (isExpanded) {
                            const chartId = `chart-${escapeHTML(fii.ticker)}`;
                            const container = document.getElementById(chartId);
                            if (container && container.children.length === 0) {
                                new TradingView.MediumWidget({
                                    "symbols": [[`${fii.ticker}`, `BMFBOVESPA:${fii.ticker}|1D`]],
                                    "chartOnly": false,
                                    "width": "100%",
                                    "height": 300,
                                    "locale": "br",
                                    "colorTheme": "dark",
                                    "autosize": true,
                                    "showVolume": false,
                                    "hideDateRanges": false,
                                    "scalePosition": "right",
                                    "scaleMode": "Normal",
                                    "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
                                    "noTimeScale": false,
                                    "valuesTracking": "1",
                                    "changeMode": "price-and-percent",
                                    "chartType": "area",
                                    "adjustment": "dividends",
                                    "container_id": chartId
                                });
                            }
                        }
                    });
                    fiiContainer.appendChild(card);
                });
            });

            // Update filter logic to hide/show headers
            const originalFilterFIIs = window.filterFIIs;
            window.filterFIIs = function (strategy, btn) {
                originalFilterFIIs(strategy, btn);
                const headers = fiiContainer.querySelectorAll('.group-header');
                headers.forEach(h => {
                    if (strategy === 'ALL') {
                        h.style.display = 'block';
                    } else if (strategy === 'SAFE_INCOME') {
                        // Safe income could be in any group, difficult to hide headers safely 
                        // without checking if any children are visible. 
                        // Let's just keep headers visible for SAFE_INCOME for now or hide if empty.
                        const visibleCards = fiiContainer.querySelectorAll(`.stock-card.fii[data-type="${h.dataset.type}"]:not([style*="display: none"])`);
                        h.style.display = visibleCards.length > 0 ? 'block' : 'none';
                    } else {
                        h.style.display = (h.dataset.type === strategy) ? 'block' : 'none';
                    }
                });
            };
            // Render Fixed Income
            const fixedContainer = document.getElementById('content-fixed');

            // 1. Private Benchmarks (shown first)
            if (data.fixedIncome && data.fixedIncome.private) {
                const title = document.createElement('h2');
                title.textContent = '🏦 Referências (Benchmarks)';
                title.style.width = '100%';
                title.style.gridColumn = '1 / -1'; // Force full width in grid
                title.style.margin = '1rem 0 0.5rem 0';
                title.style.color = 'var(--warning)';
                fixedContainer.appendChild(title);

                data.fixedIncome.private.forEach(bench => {
                    const card = document.createElement('div');
                    card.className = 'stock-card';
                    card.dataset.searchTerm = `${escapeHTML(bench.name)} ${escapeHTML(bench.type)} renda fixa`.toLowerCase();
                    card.style.borderLeftColor = 'var(--warning)';
                    card.innerHTML = `
                    <div class="ticker-info">
                        <h3>${escapeHTML(bench.name)}</h3>
                        <span>${escapeHTML(bench.type)}</span>
                    </div>
                    <div class="metrics">
                        <div class="price" style="color:var(--success)">${escapeHTML(bench.rate)}</div>
                    </div>
                `;
                    fixedContainer.appendChild(card);
                });
            }

            // 2. Tesouro Direto (shown second)
            if (data.fixedIncome && data.fixedIncome.tesouro) {
                const title = document.createElement('h2');
                title.textContent = '🏛️ Tesouro Direto';
                title.style.width = '100%';
                title.style.gridColumn = '1 / -1'; // Force full width in grid
                title.style.margin = '2rem 0 0.5rem 0';
                title.style.color = 'var(--primary)';
                fixedContainer.appendChild(title);

                data.fixedIncome.tesouro.forEach(bond => {
                    const card = document.createElement('div');
                    card.className = 'stock-card';
                    card.dataset.searchTerm = `${escapeHTML(bond.name)} tesouro`.toLowerCase();
                    card.style.borderLeftColor = 'var(--text-color)';
                    card.innerHTML = `
                    <div class="ticker-info">
                        <h3>${escapeHTML(bond.name)}</h3>
                        <span>Vence: ${escapeHTML(bond.maturity)}</span>
                    </div>
                    <div class="metrics">
                        <div class="price">${escapeHTML(bond.rate)}</div>
                        <div style="font-size:0.8rem; color:var(--text-muted)">Min: ${escapeHTML(bond.minInvest)}</div>
                    </div>
                `;
                    fixedContainer.appendChild(card);
                });
            }

            // Render Snowball Tab
            renderSnowball(data.fiis);

            // Render ETFs
            const etfContainer = document.getElementById('content-etfs');
            if (data.etfs) {
                data.etfs.forEach(etf => {
                    const card = document.createElement('div');
                    card.className = 'stock-card fii'; // Reuse FII styling for consistency
                    card.dataset.searchTerm = `${etf.ticker} etf`.toLowerCase();
                    card.style.borderLeftColor = 'var(--accent)';

                    card.innerHTML = `
                <div class="card-main">
                    <div class="ticker-info">
                        <h3>
                            <img src="https://raw.githubusercontent.com/thefintz/icones-b3/main/icones/${escapeHTML(etf.ticker)}.png"
                                 class="stock-logo" 
                                 onerror="this.style.display='none'"
                                 alt="${escapeHTML(etf.ticker)}">
                            ${escapeHTML(etf.ticker)}
                        </h3>
                        <span style="font-size:0.8rem; color:var(--text-muted)">ETF de Renda Variável</span>
                    </div>
                    <div class="metrics" style="display:flex; align-items:center; gap:12px;">
                        <div style="text-align:right">
                            <div class="price">R$ ${escapeHTML(etf.price.toFixed(2))}</div>
                            <div style="display:flex; gap:4px; justify-content:flex-end; margin-top:4px;">
                                <span class="badge ${etf.dy > 0 ? 'price-badge' : ''}">DY ${etf.dy > 0 ? escapeHTML(etf.dy.toFixed(2)) + '%' : 'N/A'}</span>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="card-details">
                    <div class="detail-grid">
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Liq. Diária</span><span class="detail-value">R$ ${escapeHTML((etf.liquidity / 1000000).toFixed(1))}M</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Var. 12m</span><span class="detail-value" style="color:${etf.variation_12m >= 0 ? 'var(--success)' : 'var(--danger)'}">${escapeHTML(etf.variation_12m.toFixed(2))}%</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Min 52s</span><span class="detail-value">R$ ${escapeHTML(etf.low_52w.toFixed(2))}</span></div>
                        </div>
                        <div class="detail-box">
                            <div class="detail-row"><span class="detail-label">Max 52s</span><span class="detail-value">R$ ${escapeHTML(etf.high_52w.toFixed(2))}</span></div>
                        </div>
                    </div>
                    <div id="chart-${escapeHTML(etf.ticker)}" class="chart-container"></div>
                    <a href="${getInvestidor10Url({ ticker: etf.ticker, type: 'ETF' })}" target="_blank" class="external-link-btn">
                        📊 Ver no Investidor 10
                    </a>
                </div>
            `;
                    card.addEventListener('click', () => {
                        const isExpanded = card.classList.toggle('expanded');
                        card.querySelector('.card-details').classList.toggle('show');

                        if (isExpanded) {
                            const chartId = `chart-${escapeHTML(etf.ticker)}`;
                            const container = document.getElementById(chartId);
                            if (container && container.children.length === 0) {
                                new TradingView.MediumWidget({
                                    "symbols": [[`${etf.ticker}`, `BMFBOVESPA:${etf.ticker}|1D`]],
                                    "chartOnly": false,
                                    "width": "100%",
                                    "height": 300,
                                    "locale": "br",
                                    "colorTheme": "dark",
                                    "autosize": true,
                                    "showVolume": false,
                                    "hideDateRanges": false,
                                    "scalePosition": "right",
                                    "scaleMode": "Normal",
                                    "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
                                    "noTimeScale": false,
                                    "valuesTracking": "1",
                                    "changeMode": "price-and-percent",
                                    "chartType": "area",
                                    "adjustment": "dividends",
                                    "container_id": chartId
                                });
                            }
                        }
                    });
                    etfContainer.appendChild(card);
                });
            }
        });

        function renderSnowball(fiis) {
            const snowballContainer = document.getElementById('content-snowball');
            snowballContainer.innerHTML = '';

            // --- SNOWBALL FILTER UI ---
            const filterContainer = document.createElement('div');
            filterContainer.className = 'opp-filters';
            filterContainer.style.marginBottom = '1.5rem';
            filterContainer.style.marginTop = '1rem';
            filterContainer.style.gridColumn = '1 / -1'; // Spans full width

            const strategies = [
                { id: 'ALL', label: 'Ver Todos' },
                { id: 'TIJOLO', label: '🧱 Tijolo' },
                { id: 'PAPEL', label: '📄 Papel' },
                { id: 'AGRO', label: '🌾 Fiagro/Agro' },
                { id: 'MULTI', label: '🔄 Multimercado' },
                { id: 'INFRA', label: '⚡ Infra' },
                { id: 'BASE10', label: '🪙 Base 10' },
                { id: 'SAFE_INCOME', label: '🛡️ Seguro' }
            ];

            strategies.forEach(s => {
                const btn = document.createElement('button');
                btn.textContent = s.label;
                btn.className = 'filter-btn ' + (s.id === 'ALL' ? 'active' : '');
                btn.onclick = () => filterSnowball(s.id, btn, fiis);
                filterContainer.appendChild(btn);
            });
            snowballContainer.appendChild(filterContainer);
            // --------------------------

            // Wrapper for list content (not strictly needed as we clear children except filter container)

            // Initial Render
            renderSnowballItems(fiis, 'ALL', snowballContainer);

            // Filter Logic
            window.filterSnowball = function (strategy, btn, allFiis) {
                // Update buttons
                const container = btn.parentNode;
                container.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Clear items only
                Array.from(snowballContainer.children).forEach(child => {
                    if (child !== filterContainer) snowballContainer.removeChild(child);
                });

                renderSnowballItems(allFiis, strategy, snowballContainer);
            };
        }

        function renderSnowballItems(fiis, strategy, container) {
            // Render Top 10 when 'Ver Todos' is active
            if (strategy === 'ALL') {
                const top10 = [...fiis]
                    .sort((a, b) => {
                        // Sort by score first (descending), then by DY (descending)
                        if (b.score !== a.score) return b.score - a.score;
                        return b.dy - a.dy;
                    })
                    .slice(0, 10);

                if (top10.length > 0) {
                    const header = document.createElement('h2');
                    header.textContent = '🏆 Top 10 Melhores FIIs';
                    header.style.color = '#FFD700'; // Gold color
                    header.style.marginTop = '1.5rem';
                    header.style.gridColumn = '1 / -1';
                    container.appendChild(header);

                    top10.forEach((fii, index) => {
                        // Safety checks for dy and price to avoid division by zero
                        const dy = fii.dy || 0;
                        const price = fii.price || 0;

                        const monthlyDiv = (price * (dy / 100)) / 12;
                        const magicNumber = fii.magicNumber || (monthlyDiv > 0 ? Math.ceil(price / monthlyDiv) : 0);
                        const totalInvest = magicNumber * price;
                        const totalMonthly = magicNumber * monthlyDiv;

                        const formatLiquidity = (value) => {
                            if (!value || value === 0) return 'N/A';
                            if (value >= 1000000) return `R$ ${(value / 1000000).toFixed(2)}M`;
                            if (value >= 1000) return `R$ ${(value / 1000).toFixed(0)}K`;
                            return `R$ ${value.toFixed(2)}`;
                        };

                        const card = document.createElement('div');
                        card.className = 'stock-card';
                        card.dataset.searchTerm = `${fii.ticker} ${fii.segment} fii bola de neve`.toLowerCase();
                        card.style.borderLeftColor = '#FFD700';
                        card.style.borderLeftWidth = '6px';

                        // Highlight AGRO/INFRA
                        if (fii.type === 'AGRO') card.style.borderRight = '4px solid #fba94c';
                        if (fii.type === 'INFRA') card.style.borderRight = '4px solid #00d4ff';

                        card.innerHTML = `
                            <div class="card-main">
                                <div class="ticker-info">
                                    <h3>
                                        <span style="color:#FFD700; font-weight:bold; margin-right:0.5rem">#${index + 1}</span>
                                        <img src="https://raw.githubusercontent.com/thefintz/icones-b3/main/icones/${escapeHTML(fii.ticker)}.png"
                                            class="stock-logo" 
                                            onerror="this.style.display='none'"
                                            alt="${escapeHTML(fii.ticker)}">
                                        ${escapeHTML(fii.ticker)}
                                        ${fii.type === 'TIJOLO' ? '<span class="badge" style="background:#7f7f7f; color:white">🧱 Tijolo</span>' : ''}
                                        ${fii.type === 'PAPEL' ? '<span class="badge" style="background:#3498db; color:white">📄 PAPEL</span>' : ''}
                                        ${fii.type === 'MULTI' ? '<span class="badge" style="background:#9b59b6; color:white">🔄 MULTI</span>' : ''}
                                        ${fii.type === 'AGRO' ? '<span class="badge" style="background:#fba94c; color:black">🌾 AGRO</span>' : ''}
                                        ${fii.type === 'INFRA' ? '<span class="badge" style="background:#00d4ff; color:black">⚡ INFRA</span>' : ''}
                                    </h3>
                                    <span style="font-size:0.75rem; color:var(--text-muted)">Com ${escapeHTML(String(magicNumber))} cotas, o dividendo paga +1 cota</span>
                                </div>
                                <div class="metrics" style="display:flex; align-items:center; gap:12px;">
                                    <div style="text-align:right">
                                        <div class="price">R$ ${escapeHTML(fii.price.toFixed(2))}</div>
                                        <div style="display:flex; gap:4px; justify-content:flex-end; margin-top:4px;">
                                            <span class="badge ${fii.dy > 8 ? 'price-badge' : ''}">DY ${escapeHTML(String(fii.dy))}%</span>
                                            <span class="badge">~R$ ${escapeHTML(monthlyDiv.toFixed(2))} /cota</span>
                                        </div>
                                    </div>
                                    <div class="score-indicator score-star" title="Meta de Cotas">
                                        <div style="display:flex; flex-direction:column; align-items:center; line-height:1;">
                                            <span style="font-size:0.6rem; color:var(--text-muted)">META</span>
                                            <span>${escapeHTML(String(magicNumber))}</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div class="card-details">
                                <div class="detail-grid">
                                    <div class="detail-box">
                                        <div class="detail-row"><span class="detail-label">Invest. Total (Meta)</span><span class="detail-value" style="color:var(--warning)">R$ ${escapeHTML(totalInvest.toLocaleString('pt-BR', { minimumFractionDigits: 2 }))}</span></div>
                                    </div>
                                    <div class="detail-box">
                                        <div class="detail-row"><span class="detail-label">Renda Anual (Meta)</span><span class="detail-value">R$ ${escapeHTML((totalMonthly * 12).toLocaleString('pt-BR', { minimumFractionDigits: 2 }))}</span></div>
                                    </div>
                                    <div class="detail-box">
                                        <div class="detail-row"><span class="detail-label">Renda Mensal (Meta)</span><span class="detail-value" style="color:var(--success)">R$ ${escapeHTML(totalMonthly.toLocaleString('pt-BR', { minimumFractionDigits: 2 }))}</span></div>
                                    </div>
                                    <div class="detail-box">
                                        <div class="detail-row"><span class="detail-label">Último Rendimento</span><span class="detail-value" style="color:var(--success)">${fii.last_dividend ? `R$ ${escapeHTML(fii.last_dividend.toFixed(2))}` : 'N/A'}</span></div>
                                    </div>
                                    <div class="detail-box">
                                        <div class="detail-row"><span class="detail-label">Liq. Diária</span><span class="detail-value" style="color:var(--accent)">${escapeHTML(formatLiquidity(fii.liquidity))}</span></div>
                                    </div>
                                    <div class="detail-box">
                                        <div class="detail-row"><span class="detail-label">P/VP</span><span class="detail-value">${escapeHTML((fii.p_vp || fii.pvp || 0).toFixed(2))}</span></div>
                                    </div>
                                </div>

                                <div class="detail-row" style="flex-direction:row; justify-content:space-between; margin-bottom:8px;">
                                    <span class="detail-label">Última Data Com:</span>
                                    <span class="detail-value" style="color:var(--warning)">${fii.data_com || 'N/A'}</span>
                                </div>
                                <div class="detail-row" style="flex-direction:row; justify-content:space-between; margin-bottom:8px;">
                                    <span class="detail-label">Último Pagamento:</span>
                                    <span class="detail-value" style="color:var(--success)">${fii.data_pagamento || 'N/A'}</span>
                                </div>
                                <div id="chart-snow-top-${escapeHTML(fii.ticker)}" class="chart-container"></div>
                                <a href="${getInvestidor10Url(fii)}" target="_blank" class="external-link-btn">
                                    📊 Ver no Investidor 10
                                </a>
                            </div>
                        `;

                        card.addEventListener('click', () => {
                            const isExpanded = card.classList.toggle('expanded');
                            card.querySelector('.card-details').classList.toggle('show');

                            if (isExpanded) {
                                const chartId = `chart-snow-top-${escapeHTML(fii.ticker)}`;
                                const container = document.getElementById(chartId);
                                if (container && !container.hasChildNodes()) {
                                    new TradingView.widget({
                                        "autosize": true,
                                        "symbol": `BMFBOVESPA:${fii.ticker}`,
                                        "interval": "D",
                                        "timezone": "America/Sao_Paulo",
                                        "theme": "dark",
                                        "style": "1",
                                        "locale": "br",
                                        "toolbar_bg": "#f1f3f6",
                                        "enable_publishing": false,
                                        "adjustment": "dividends",
                                        "container_id": chartId
                                    });
                                }
                            }
                        });

                        container.appendChild(card);
                    });
                }
            }

            const sections = [
                { title: '⚡ Destaques (Fiagro & Infra)', filter: f => f.type === 'AGRO' || f.type === 'INFRA', color: '#00d4ff', showOnlyWhenFiltered: true },
                { title: '🪙 Base R$ 10 (Acessíveis)', filter: f => f.price < 15, color: '#fba94c' },
                { title: '⚖️ Base R$ 20 - R$ 50 (Intermediários)', filter: f => f.price >= 15 && f.price < 70, color: '#8257e5' },
                { title: '💎 Base R$ 100+ (Premium/Tradicionais)', filter: f => f.price >= 70, color: '#04d361' }
            ];

            sections.forEach(section => {
                // Skip Destaques section when 'Ver Todos' is active
                if (section.showOnlyWhenFiltered && strategy === 'ALL') return;

                // 1. Filter by Section (Price or Type)
                let filtered = fiis.filter(section.filter);

                // 2. Filter by Strategy/Type
                if (strategy !== 'ALL') {
                    if (strategy === 'BASE10') {
                        if (!section.title.includes('Base R$ 10')) filtered = [];
                    } else if (strategy === 'SAFE_INCOME') {
                        filtered = filtered.filter(f => f.strategies.includes('SAFE_INCOME'));
                    } else {
                        // For TIJOLO, PAPEL, AGRO, INFRA, MULTI -> Filter by TYPE
                        filtered = filtered.filter(f => f.type === strategy);
                    }
                }

                if (filtered.length === 0) return;

                const header = document.createElement('h2');
                header.textContent = section.title;
                header.style.gridColumn = '1 / -1';
                header.style.color = section.color;
                header.style.marginTop = '1.5rem';
                container.appendChild(header);

                filtered.forEach(fii => {
                    // Safety checks for dy and price to avoid division by zero
                    const dy = fii.dy || 0;
                    const price = fii.price || 0;

                    const monthlyDiv = (price * (dy / 100)) / 12;
                    const magicNumber = fii.magicNumber || (monthlyDiv > 0 ? Math.ceil(price / monthlyDiv) : 0);
                    const totalInvest = magicNumber * price;
                    const totalMonthly = magicNumber * monthlyDiv;

                    // Format liquidity
                    const formatLiquidity = (value) => {
                        if (!value || value === 0) return 'N/A';
                        if (value >= 1000000) return `R$ ${(value / 1000000).toFixed(2)}M`;
                        if (value >= 1000) return `R$ ${(value / 1000).toFixed(0)}K`;
                        return `R$ ${value.toFixed(2)}`;
                    };

                    const card = document.createElement('div');
                    card.className = 'stock-card';
                    card.dataset.searchTerm = `${fii.ticker} ${fii.segment} fii bola de neve`.toLowerCase();
                    card.style.borderLeftColor = section.color;

                    // Highlight AGRO/INFRA
                    if (fii.type === 'AGRO') card.style.borderRight = '4px solid #fba94c'; // Orange for Agro
                    if (fii.type === 'INFRA') card.style.borderRight = '4px solid #00d4ff'; // Blue for Infra

                    card.innerHTML = `
                        <div class="card-main">
                            <div class="ticker-info">
                                <h3>
                                    <img src="https://raw.githubusercontent.com/thefintz/icones-b3/main/icones/${escapeHTML(fii.ticker)}.png"
                                        class="stock-logo" 
                                        onerror="this.style.display='none'"
                                        alt="${escapeHTML(fii.ticker)}">
                                    ${escapeHTML(fii.ticker)}
                                    ${fii.type === 'TIJOLO' ? '<span class="badge" style="background:#7f7f7f; color:white">🧱 Tijolo</span>' : ''}
                                    ${fii.type === 'PAPEL' ? '<span class="badge" style="background:#3498db; color:white">📄 Papel</span>' : ''}
                                    ${fii.type === 'MULTI' ? '<span class="badge" style="background:#9b59b6; color:white">🔄 Multi</span>' : ''}
                                    ${fii.type === 'AGRO' ? '<span class="badge" style="background:#fba94c; color:black">🌾 Agro</span>' : ''}
                                    ${fii.type === 'INFRA' ? '<span class="badge" style="background:#00d4ff; color:black">⚡ Infra</span>' : ''}
                                </h3>
                                <span style="font-size:0.75rem; color:var(--text-muted)">Com ${escapeHTML(String(magicNumber))} cotas, o dividendo paga +1 cota</span>
                            </div>
                            <div class="metrics" style="display:flex; align-items:center; gap:12px;">
                                <div style="text-align:right">
                                    <div class="price">R$ ${escapeHTML(fii.price.toFixed(2))}</div>
                                    <div style="display:flex; gap:4px; justify-content:flex-end; margin-top:4px;">
                                        <span class="badge ${fii.dy > 8 ? 'price-badge' : ''}">DY ${escapeHTML(String(fii.dy))}%</span>
                                        <span class="badge">~R$ ${escapeHTML(monthlyDiv.toFixed(2))} /cota</span>
                                    </div>
                                </div>
                                <div class="score-indicator score-star" title="Meta de Cotas" style="border-color:${section.color}; color:${section.color}">
                                    <div style="display:flex; flex-direction:column; align-items:center; line-height:1;">
                                        <span style="font-size:0.6rem; color:var(--text-muted)">META</span>
                                        <span>${escapeHTML(String(magicNumber))}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="card-details">
                            <div class="detail-grid">
                                <div class="detail-box">
                                    <div class="detail-row"><span class="detail-label">Invest. Total (Meta)</span><span class="detail-value" style="color:var(--warning)">R$ ${escapeHTML(totalInvest.toLocaleString('pt-BR', { minimumFractionDigits: 2 }))}</span></div>
                                </div>
                                <div class="detail-box">
                                    <div class="detail-row"><span class="detail-label">Renda Anual (Meta)</span><span class="detail-value">R$ ${escapeHTML((totalMonthly * 12).toLocaleString('pt-BR', { minimumFractionDigits: 2 }))}</span></div>
                                </div>
                                <div class="detail-box">
                                    <div class="detail-row"><span class="detail-label">Renda Mensal (Meta)</span><span class="detail-value" style="color:var(--success)">R$ ${escapeHTML(totalMonthly.toLocaleString('pt-BR', { minimumFractionDigits: 2 }))}</span></div>
                                </div>
                                <div class="detail-box">
                                    <div class="detail-row"><span class="detail-label">Último Rendimento</span><span class="detail-value" style="color:var(--success)">${fii.last_dividend ? `R$ ${escapeHTML(fii.last_dividend.toFixed(2))}` : 'N/A'}</span></div>
                                </div>
                                <div class="detail-box">
                                    <div class="detail-row"><span class="detail-label">Liq. Diária</span><span class="detail-value" style="color:var(--accent)">${escapeHTML(formatLiquidity(fii.liquidity))}</span></div>
                                </div>
                                <div class="detail-box">
                                    <div class="detail-row"><span class="detail-label">P/VP</span><span class="detail-value">${escapeHTML((fii.p_vp || fii.pvp || 0).toFixed(2))}</span></div>
                                </div>
                            </div>
                            
                            <div class="detail-row" style="flex-direction:row; justify-content:space-between; margin-bottom:8px;">
                                <span class="detail-label">Última Data Com:</span>
                                <span class="detail-value" style="color:var(--warning)">${fii.data_com || 'N/A'}</span>
                            </div>
                            <div class="detail-row" style="flex-direction:row; justify-content:space-between; margin-bottom:8px;">
                                <span class="detail-label">Último Pagamento:</span>
                                <span class="detail-value" style="color:var(--success)">${fii.data_pagamento || 'N/A'}</span>
                            </div>
                            <div id="chart-snow-${escapeHTML(fii.ticker)}" class="chart-container"></div>
                            <a href="${getInvestidor10Url(fii)}" target="_blank" class="external-link-btn">
                                📊 Ver no Investidor 10
                            </a>
                        </div>
                    `;

                    card.addEventListener('click', () => {
                        const isExpanded = card.classList.toggle('expanded');
                        card.querySelector('.card-details').classList.toggle('show');

                        if (isExpanded) {
                            const chartId = `chart - snow - ${escapeHTML(fii.ticker)} `;
                            const container = document.getElementById(chartId);
                            if (container && container.children.length === 0) {
                                new TradingView.MediumWidget({
                                    "symbols": [[`${fii.ticker} `, `BMFBOVESPA:${fii.ticker}| 1D`]],
                                    "chartOnly": false,
                                    "width": "100%",
                                    "height": 300,
                                    "locale": "br",
                                    "colorTheme": "dark",
                                    "autosize": true,
                                    "adjustment": "dividends",
                                    "container_id": chartId
                                });
                            }
                        }
                    });

                    container.appendChild(card);
                });
            });
        }

        function showTab(tabName) {
            // Hide all
            ['stocks', 'fiis', 'snowball', 'fixed', 'etfs'].forEach(t => {
                document.getElementById(`content - ${t} `).classList.add('hidden');
            });
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

            // Show selected
            document.getElementById(`content - ${tabName} `).classList.remove('hidden');

            // Highlight active tab
            document.querySelectorAll('.tab-btn').forEach(btn => {
                if (btn.textContent.toLowerCase().includes(tabName === 'snowball' ? 'bola de neve' : tabName)) {
                    btn.classList.add('active');
                }
            });
        }

        function getInvestidor10Url(item) {
            const ticker = (item.ticker || item.Ticker || '').toLowerCase();
            const type = item.type;
            if (type === 'AGRO') return `https://investidor10.com.br/fiagros/${ticker}/`;
            if (type === 'ETF') return `https://investidor10.com.br/etfs/${ticker}/`;
            if (ticker && !type) return `https://investidor10.com.br/acoes/${ticker}/`;
            return `https://investidor10.com.br/fiis/${ticker}/`;
        }
    