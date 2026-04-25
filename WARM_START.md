# 🚀 Warm Start — Guia de Treinamento e Deploy de Modelos

Ver documentação completa em: /home/ayu/.gemini/antigravity/brain/5bb22670-6b33-46fa-a2b6-2f0bcf392e76/warm_start_guide.md

## Início Rápido

```bash
# 1. Gerar modelos pré-treinados (5000 velas por ativo)
export PYTHONPATH=$PYTHONPATH:.
python3 scripts/warm_start.py

# 2. Validar integridade (102 testes)
pytest tests/unit/test_warm_start_models.py -v

# 3. Sincronizar com servidor remoto
sshpass -p 1597 scp -r -o StrictHostKeyChecking=no models/ docker-compose.yml diogo@100.86.220.116:Documents/Btc_bot/
sshpass -p 1597 ssh -o StrictHostKeyChecking=no diogo@100.86.220.116 "cd Documents/Btc_bot && docker compose up -d"
```
