# Advanced Multicore BTC Bot & MiroFish Integration

Este projeto combina um robô de trading multicore baseado em Machine Learning com a engine de análise de sentimento social **MiroFish**.

## 🚀 Como Funciona

O sistema opera em três camadas (Tiers):

1.  **Tier 1: Portfolio/Inventory**: Exibe em tempo real o seu **Patrimônio Total (Equity)**, separando o que é saldo líquido (Cash) do valor investido nas moedas (BTC, ETH, SOL).
2.  **Tier 2: Cofre (Basis Arbitrage)**: Monitora oportunidades de arbitragem entre o preço Spot e Futuro para garantir rendimentos fixos em BRL caso a estratégia principal esteja neutra.
3.  **Tier 3: Alpha (ML Engine)**: Utiliza modelos de Random Forest treinados com dados históricos para prever a direção do preço com base em indicadores técnicos e fluxo de ordens.
    *   **Viés MiroFish**: Se a MiroFish detectar um sentimento "Bullish", o robô ganha um bônus de confiança para compras. Se "Bearish", o bônus vai para vendas.

## 🛠️ Como Rodar (VPS)

O projeto está totalmente Dockerizado. Para iniciar ou atualizar:

```bash
# Navegue até a pasta do projeto
cd ~/Btc_bot

# Inicie os serviços (MiroFish + Bot)
docker compose up -d --build
```

### Comandos Úteis

*   **Ver Logs do Bot**: `docker compose logs -f btc-master-bot`
*   **Ver Logs da MiroFish**: `docker compose logs -f mirofish`
*   **Reiniciar tudo**: `docker compose restart`
*   **Resetar Saldo**: Pare o bot, edite `Advanced_Btc_Bot/results/balance_state.txt` para `1000.0` e `results/bot_status.json` para `{}` nas posições, depois inicie.

## 📝 Monitoramento

O painel do bot exibe:
- **Equity**: Seu valor total real (Saldo + Moedas).
- **Saldo Disponível**: Dinheiro livre para novas operações.
- **Portfolio**: Lista de moedas em carteira, quantidade e PnL individual.

## ⚙️ Configuração (.env)

Certifique-se de configurar as chaves no arquivo `.env` na raiz:
- `BINANCE_API_KEY` / `BINANCE_SECRET_KEY`
- `MIROFISH_API_URL` (Geralmente `http://mirofish:8000/api` no Docker)
- Configurações da MiroFish em `MiroFish/.env` (LLM Key, etc).

---
##Leia o arquivo para entender o projeto:
`C:\Nestjs\Btc_bot\antigravity.md`
---
*Desenvolvido para DiogoCrespi - Quant Integration v2.0*
