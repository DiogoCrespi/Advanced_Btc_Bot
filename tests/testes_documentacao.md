# Documentação de Testes - Btc_bot

Este documento descreve os testes implementados para garantir a robustez e a lucratividade do bot de trading multicarteira. Conforme a filosofia de engenharia do projeto, **testes não são feitos apenas para passar, mas para testar limites e falhas esperadas.**

---

## 1. Visão Geral dos Testes

Os testes estão divididos em categorias de intenção:
- ✅ **Sucesso Esperado (Caminho Feliz)**: Valida se a lógica lucra e identifica sinais corretamente em condições ideais.
- ❌ **Falha/Rejeição Esperada (Caminho de Segurança)**: Valida se o bot rejeita dados corrompidos, saldo insuficiente ou riscos excessivos sem crashar.
- 🎯 **Diferenciação de Oportunidades**: Valida se o bot sabe distinguir entre ruído de mercado e oportunidades de alta convicção.

---

## 2. Detalhamento por Tier

### Tier 1: Arbitragem de Basis (Cofre)
- **Objetivo**: Arbitragem Spot/Futuro em BRL.
- ✅ **Sucesso**: `test_basis_calculation` - Cálculo de Yield % positivo em contango.
- ❌ **Rejeição**: `test_basis_zero_price_handling` - Deve retornar Yield 0 se o preço for zero, impedindo divisão por zero.

### Tier 2: Alpha ML (Trade Direcional)
- **Objetivo**: Trade via IA e Order Flow.
- ✅ **Sucesso**: `test_ml_train_predict` - Modelo treina e gera sinal 1/-1 com dados limpos.
- ❌ **Rejeição**: `test_ml_brain_nan_inf_handling` - Deve retornar sinal 0 (Neutro) se as features contiverem `NaN` ou `Inf`.

### Tier 3: Rotação XAUT/BTC
- **Objetivo**: Acumular BTC via Ouro Digital.
- ✅ **Sucesso**: `test_xaut_buy_signal` - Compra XAUT quando o ratio está em sobrevenda.
- ❌ **Rejeição**: `test_xaut_dca_rejection` - Deve recusar nova entrada (`is_dca_allowed = False`) se estiver muito próxima do preço de entrada anterior.

---

## 3. Oportunidades vs Riscos (Gaps)
**Arquivo**: `tests/unit/test_opportunities.py`

| Caso de Teste | Descrição | Classificação | Resultado Esperado |
| :--- | :--- | :--- | :--- |
| **Real Opportunity** | Breakaway Gap com volume 5x, alinhado à SMA50 e CVD positivo. | `Breakaway` | `is_opportunity = True` (Convicção ≥ 0.7) |
| **Exhaustion Risk** | Gap no final de tendência esticada (>5%) com volume extremo. | `Exhaustion` | `is_opportunity = False` (Penalização Máxima) |
| **Common Gap** | Gap pequeno (<1%) com volume baixo. | `Common` | `is_opportunity = False` (Baixa Convicção) |

---

## 4. Como Executar os Testes

Para rodar a suíte completa (incluindo testes de oportunidade):
```bash
pytest tests/
```

> [!NOTE]
> Um teste que "Passa" no Pytest pode ser um teste que verificou com sucesso que uma falsa oportunidade foi ignorada ou um risco foi mitigado. Verifique as mensagens de log para detalhes sobre a pontuação de convicção.
