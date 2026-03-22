**Prompt Mestre** 
---
atue como um **Arquiteto de Software Sênior** e refatore seu código usando essas referências.

---

### **IA:**

```text
Você agora é um Arquiteto de Software Sênior especializado em Fintech e Node.js.

Eu tenho um projeto chamado "b3_screener" (já carregado no seu contexto) que é um rastreador de ações e FIIs da bolsa brasileira. O objetivo dele é filtrar ativos com base em análise fundamentalista (Graham, Bazin, Greenblatt).

Acabei de adicionar uma pasta chamada "REFERENCIAS" com códigos de outros projetos open-source (Stock-Screener-bovespa, finviz-screener, etc.).

SUA MISSÃO:
Analisar o meu código atual e, usando os projetos da pasta REFERENCIAS como "banco de peças" e inspiração, reescrever e aprimorar meu sistema.

---

### PASSO 1: ANÁLISE PROFUNDA (Pense passo a passo)
1. Analise meu `screener.js` atual. Ele é funcional, mas imperativo e difícil de expandir.
2. Olhe para o projeto `finviz-screener` nas REFERENCIAS. Observe como eles usam uma "Fluent Interface" (ex: `.sector().price().scan()`). Quero que você planeje como transformar meu código para esse padrão Orientado a Objetos.
3. Olhe para o `Stock-Screener-bovespa`. Veja como eles tratam os erros de extração de dados (scraping) do Fundamentus/Investidor10. Compare com os meus `adapters` e liste mentalmente onde meu código pode quebrar se o site mudar.
4. Olhe para o `analise-de-ativos-b3`. Eles usam lógica preditiva ou estatística? Se sim, pense em como posso adicionar um campo "Tendência" (Trend) no meu output.

---

### PASSO 2: EXECUÇÃO E REFATORAÇÃO (Gere o Código)

Agora, quero que você gere as modificações reais. Não quero apenas dicas, quero código pronto para substituir os arquivos.

**Tarefa A: A Nova Arquitetura (`screener.js` e `Screener.js`)**
Crie uma classe `Screener` que permita eu filtrar ações assim no meu `index.js`:
```javascript
const results = await new Screener()
    .assetType('stock') // ou 'fii'
    .minLiquidity(200000)
    .minYield(6)
    .maxP_VP(1.2) // Aceita teto
    .excludeStrategies(['DISTRESSED_RISK']) // Tira os micos
    .run();

```

*Inspire-se fortemente na estrutura do `finviz-screener`.*

**Tarefa B: Lógica Financeira Aprimorada (`services/logic/stock-rules.js` e `fiis.js`)**
Reescreva minhas regras de pontuação (Score 0-10) para corrigir as falhas graves atuais:

1. **FIIs de Papel:** Penalize P/VP < 0.85 (Risco de Calote), em vez de premiar como "Oportunidade".
2. **Dividend Yield:** Implemente o "Capping" (Teto). Se o DY for > 16%, considere apenas 16% para o cálculo do score e adicione uma flag de alerta "HIGH_VOLATILITY".
3. **Tendência (Inovação):** Adicione uma verificação simples: Se (Lucro Atual < Lucro 5 Anos Atrás), penalize o score em 3 pontos.

**Tarefa C: Persistência (`services/storage.js`)**
Baseado no `node-stock-data`, crie um módulo simples que salva o resultado de cada execução em um arquivo JSON com data (`history/2023-10-27-results.json`). Isso é vital para eu validar se o script acerta ao longo do tempo.

---

### REGRAS PARA SUA RESPOSTA:

1. **Não apague meus adapters** (`brapi-stock-adapter.js`, etc.) a menos que eles estejam errados. Eles funcionam. Apenas melhore como os dados deles são *processados*.
2. **Seja Modular:** Se criar um arquivo novo, diga exatamente onde salvar.
3. **Explique o Porquê:** Antes de cada bloco de código, diga: "Estou alterando isso porque no projeto de referência X eles fazem Y, que é mais seguro/rápido".

Comece agora pela **Tarefa A (Arquitetura)**. Mostre a nova classe `Screener`.

```

---
