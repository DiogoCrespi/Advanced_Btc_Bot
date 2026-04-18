# 🛡️ Análise de Riscos e Plano de Melhorias (Live Trading)

Este documento detalha as vulnerabilidades identificadas no motor do **Advanced BTC Bot** e as melhorias necessárias para operação em conta real. 

> [!IMPORTANT]
> **Decisão Estratégica:** O componente **MiroFish** foi oficialmente descontinuado e não será utilizado nesta arquitetura. Toda a inteligência e análise de sentimento serão migradas para processamento local ou oráculos alternativos diretos.

---

## 🛑 Riscos de Execução (Prejuízos Imediatos)

### 1. Slippage e Liquidez (Pares BRL)
*   **Problema:** Uso exclusivo de `MARKET ORDERS` em pares como BTCBRL e SOLBRL.
*   **Impacto:** Execução a preços desfavoráveis em momentos de volatilidade, reduzindo a eficiência do Take Profit.
*   **Melhoria:** Implementar `LIMIT ORDERS` com algoritmos de execução (ex: post-only e retries).
*   **Status:** [CONCLUÍDO] Implementado o módulo `LimitExecutor`:
    *   **Post-Only:** Utiliza `LIMIT_MAKER` para garantir que o bot seja sempre prover de liquidez (taxas menores e zero slippage negativo).
    *   **Smart Retries:** Monitora o Order Book e reposiciona a ordem caso o preço se distancie do Bid/Ask.
    *   **Fallback:** Sistema de fallback para Market Order em caso de falhas críticas de preenchimento.

### 2. Deriva de Saldo (Local vs. Exchange)
*   **Problema:** O bot controla o saldo de forma teórica em memória (`self.balance`), sem sincronização frequente com a API.
*   **Impacto:** Erros de cálculo de alocação e falhas de ordem por insuficiência de fundos real.
*   **Melhoria:** Sincronização atômica do saldo a cada ciclo de trade ou intervalo fixo.
*   **Status:** [CONCLUÍDO] Implementada abordagem híbrida:
    *   **REST API:** Sincronização forçada no startup e a cada 15 minutos (reconciliação).
    *   **Websocket (User Data Stream):** Atualizações em tempo real (`outboundAccountPosition`) integradas ao `WebSocketSupervisor`.

### 3. Falta de Confirmação de Ordem
*   **Problema:** O código atual assume que a ordem foi executada com sucesso ao atualizar o estado interno.
*   **Impacto:** Se a ordem falhar ou ficar pendente, o bot perde o controle sobre a exposição real do capital.
*   **Melhoria:** Loop de verificação de status da ordem (`FILLED`, `CANCELED`, `PARTIALLY_FILLED`) antes de atualizar o banco local.
*   **Status:** [CONCLUÍDO] Implementado loop de polling no `LimitExecutor` que aguarda o status `FILLED` via `get_order_status` antes de confirmar a transação para o motor principal.

---

## 📉 Gerenciamento de Risco e Capital

### 1. Stop Loss Estático (Inercial)
*   **Problema:** Stop Loss e Take Profit são porcentagens fixas que não respiram com o mercado.
*   **Impacto:** *Stop-out* desnecessário em alta volatilidade (ruído) e alvos curtos demais em tendências fortes.
*   **Melhoria:** Adoção de **ATR (Average True Range)** para calcular paradas dinâmicas baseadas na volatilidade.
*   **Status:** [CONCLUÍDO] Implementado cálculo de ATR no `DataEngine` e lógica de stop dinâmico no `RiskManager`. O bot agora ajusta a distância do stop baseado na volatilidade real do ativo (Multiplier: 2.0x ATR), protegendo o capital sem ser "violinado" por ruído.

### 2. Criterio de Kelly Sem Calibração
*   **Problema:** O dimensionamento das mãos depende da acurácia informada pelo modelo de ML.
*   **Impacto:** Se o modelo estiver "overfitted" ou muito confiante, o bot alocará capital excessivo, aumentando o risco de ruína.
*   **Melhoria:** Implementar um multiplicador de "Ego" que reduz o Kelly automaticamente se o *Drawdown* diário aumentar.
*   **Status:** [CONCLUÍDO] Implementada Calibração Dinâmica de "Ego":
    *   O bot monitora a acurácia real dos últimos 20 trades via `Ledger`.
    *   Se a acurácia real for inferior à esperada pelos modelos em mais de 10%, o `ego_multiplier` é reduzido, diminuindo o tamanho das próximas mãos automaticamente.
    *   O multiplicador é restaurado gradualmente conforme a performance volta a se alinhar com as expectativas.

---

## ⚙️ Estabilidade Operacional

### 1. Persistência de Estado e Robustez
*   **Problema:** Uso de arquivos `.txt` e `.json` para salvar saldo e estados. Risco de corrupção de dados e perda de histórico de trades em caso de crash.
*   **Melhoria:** Migrar para uma arquitetura de banco de dados (SQLite/Neo4j).
*   **Status:** [CONCLUÍDO] Implementada Arquitetura de Persistência Híbrida:
    *   **Ledger (SQLite):** Banco relacional para controle financeiro estrito (Saldo, Posições Ativas, Histórico de Trades). Garante integridade via ACID.

---

## 🧠 Inteligência de Mercado (v3 - Microestrutura)

### 1. Ingestão de Order Flow & Delta [IMPLEMENTADO]
*   **Problema:** Indicadores técnicos tradicionais (RSI, MACD) são reativos (atrasados).
*   **Melhoria:** Implementado o motor de **Order Flow Logic**.
    *   **Volume Delta:** Mede a agressão líquida de compradores vs vendedores.
    *   **CVD (Cumulative Volume Delta):** Rastreia a tendência de acumulação institucional.
    *   **Divergência Delta:** Detecta absorção de ordens (Price Up / Delta Down).
*   **Status:** [ATIVO] Integrado ao `DataEngine` e `MLBrain`.

### 2. Order Book Imbalance (Oráculo de Execução) [ATIVO]
*   **Problema:** Injetar Imbalance no ML sem histórico causa "envenenamento de feature" (importância zero).
*   **Estratégia:** Removido do MLBrain e transferido para o **StrategistAgent** como uma trava determinística.
*   **Lógica de Veto:** 
    *   Rejeita COMPRA se houver muralha de venda (`imbalance < -0.20`).
    *   Rejeita VENDA se houver suporte massivo de compra (`imbalance > 0.20`).
*   **Status:** [OPERACIONAL] Atuando como gatekeeper de alta fidelidade no loop de execução.
    *   **Market Memory (Neo4j):** Grafo de conhecimento que agora registra cada trade vinculado ao contexto macro e sentimento da época. Transforma o histórico financeiro em inteligência contextual.


---

## ✂️ Remoção do MiroFish

A remoção do MiroFish impacta os seguintes módulos:
*   **`multicore_master_bot.py`:** Limpeza das flags `use_mirofish` e remoção da inicialização do client.
*   **`logic/local_oracle.py`:** Refatoração para remover dependências de sentimentos externos e focar em análise técnica pura ou LLMs locais (Ollama).
*   **Arquitetura:** Simplificação do `docker-compose.yml` e redução de custo de API.

---
*Análise gerada por Antigravity AI Engine v2.4*
