# 🧠 Memória Técnica: Sessão de Engenharia v3-Alpha

Este documento serve como checkpoint de contexto para a transição do bot para a arquitetura de **Micro-Rompimento (v3-Alpha)**.

## 🎯 Objetivo da Sessão
Evoluir o motor de ML para capturar *Alpha* institucional através de Order Flow em regimes de alta volatilidade, utilizando labels de curto prazo (4h) e filtragem dinâmica de ruído (ATR Gating).

## 🛠️ Implementações Realizadas

### 1. MLBrain (Cérebro v3-Alpha)
- **Gating de Volatilidade:** Implementado `atr_threshold` móvel (Percentil 60 das últimas 1000h). O modelo veta sinais automaticamente se `feat_atr_pct` for menor que o limiar.
- **Horizonte de Alpha:** Redução do Triple Barrier para **4 horas** (Alpha Decay capture).
- **Hiperparâmetros:** Otimizados para `max_depth=11` e `min_samples_leaf=40` com `balanced_subsample` para evitar overfitting.
- **Stationarity:** Remoção de indicadores baseados em escala absoluta (Bollinger Bands brutas) em favor de métricas percentuais.

### 2. Infraestrutura de Dados & Treino
- **DataEngine:** Refatorado para suportar paginação massiva (10.000+ candles) e normalização de ATR.
- **scripts/train_model.py:** Padronizado para gerar modelos `v3_alpha` específicos por ativo (BTCBRL, ETHBRL, SOLBRL).
- **Consistência:** Garante que a matriz de features de treino seja idêntica à de predição em tempo real.

### 3. Shadow Trading & Gatekeeping
- **MulticoreMasterBot:** Integrado o loop de predição de sombra. Os sinais do v3-Alpha são logados e processados, mas não executados financeiramente na v2.
- **StrategistAgent (Patch):** Implementado override de threshold. Sinais identificados como `v3-Alpha` ou `Breakout` são aprovados com confiança **> 0.50** (em vez do padrão 0.60), alinhando-se à matemática de payoff assimétrico.
- **Propagação de Reason:** Correção no tribunal para preservar a string `"Breakout v3-Alpha"` nos logs e na decisão do agente.

## 📊 Resultados do Sandbox (v4 Validation)
- **BTCUSDT:** Precisão de **30.83%** (2.4x superior ao baseline aleatório).
- **ETHUSDT:** Precisão de **38.39%** (Presença forte de CVD 8h no Top 3 features).
- **Regime:** O filtro de regime eliminou 60% do ruído lateral, focando apenas onde o Order Flow é preditivo.

## 🚦 Estado Atual: QUARENTENA 100% OPERACIONAL
- O bot está rodando em **Shadow Mode** no ambiente Linux.
- Os modelos `v3_alpha` estão ativos para BTC, ETH e SOL.
- **Code Freeze:** A camada v2 (produção) está selada e protegida.

## ⏭️ Próximos Passos (Pós-24h)
1.  **Auditoria:** Executar `python3 scripts/audit_v3_shadow.py` para extrair métricas de precisão real do Neo4j.
2.  **Go/No-Go:** Se a Precision real for > 30%, proceder com a virada de chave para produção financeira.
3.  **Transfer Learning:** Reavaliar a necessidade de retreino se o mercado mudar drasticamente de regime.

---
*Assinado: Antigravity (IA Technical Lead)*
