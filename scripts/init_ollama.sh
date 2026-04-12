#!/bin/bash
echo "Esperando o Ollama iniciar..."
until curl -s http://ollama:11434/api/tags > /dev/null; do
  sleep 2
done

echo "Baixando o modelo leve phi3:mini..."
docker exec btc_ollama_fallback ollama pull phi3:mini
echo "Ollama pronto com phi3:mini."
