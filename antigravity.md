# 🌌 AntiGravity Project Index

Este arquivo é o seu guia central para a documentação do projeto **Btc_bot**. Aqui você encontrará links diretos para todos os arquivos Markdown (.md) importantes no repositório.

## 📂 Documentação de Arquivos
- [📖 README Geral](README.md) - O ponto de partida para entender o projeto.
- [🚀 Bolt Setup](.jules/bolt.md) - Instruções sobre o ambiente Bolt/Jules.

## 🏗️ Arquitetura e Componentes Principais

O projeto é um bot de trading avançado que utiliza múltiplas estratégias contemporâneas:

### 1. Orquestrador Core (`multicore_master_bot.py`)
O motor executivo que coordena todas as operações.
- **Concorrência**: Utiliza `ThreadPoolExecutor` para monitorar BTC, ETH e SOL em paralelo.
- **Simulação Realista**: Paper trading configurado com taxas da Binance e lógica de Stop Loss/Take Profit.
- **Persistência**: Mantém o estado atual (saldo, posições abertas) em `results/bot_status.json`.

### 2. Predictive Engine (`logic/ml_brain.py`)
Utiliza Inteligência Artificial para antecipar movimentos de preço.
- **Random Forest**: Modelo treinado com indicadores técnicos e dados de Order Flow.
- **Triple Barrier Method**: Técnica avançada de rotulagem (labeling) para ML financeiro.
- **Sazonalidade**: Considera a hora do dia e o dia da semana para capturar padrões temporais.

### 3. Lógica de Trading (`logic/`)
- **Order Flow (`order_flow_logic.py`)**: Analisa desequilíbrios na pressão de compra/venda.
- **Sentiment Analysis (`mirofish_client.py`)**: Integra uma camada extra de confiança baseada em sentimento macro via API MiroFish.
- **Cofre BRL (`basis_logic.py`)**: Detecta janelas de arbitragem de taxa livre de risco entre spot e futuros.

### 4. Gestão de Dados e Infraestrutura
- **Data Engine (`data/data_engine.py`)**: Componente central para ingestão e limpeza de dados.
- **Monitoramento (`monitor.py`)**: Script dedicado ao acompanhamento da saúde do bot.
- **Containerização**: Suporte completo para Docker e Docker Compose.

## 🛠️ Módulos Adicionais
- [🐟 MiroFish README](MiroFish/README.md) - Documentação principal do componente MiroFish de inteligência coletiva (Vue/Go/Python).
- [🌍 MiroFish (EN)](MiroFish/README-EN.md) - English documentation for MiroFish.


---
*Este índice foi criado para facilitar a navegação pelo projeto. Se novos arquivos `.md` forem adicionados, sinta-se à vontade para atualizar este arquivo!*

> **Nota:** Criado por AntiGravity 🚀
