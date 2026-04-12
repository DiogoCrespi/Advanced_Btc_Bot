# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import asyncio
import logging
import os
import requests
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger("LocalOracle")

class LocalOracle:
    """
    Motor de Sentimento Local utilizando 'Slow Track' para evitar o bloqueio 
    do motor de trade de alta frequencia do bot principal.
    Simula 3 Personas usando LLMs locais (ex: Ollama com Gemma/FinGPT).
    """

    def __init__(self, memory_module, shared_state: dict):
        self.memory = memory_module
        self.state = shared_state
        self.executor = ThreadPoolExecutor(max_workers=3) # Uma thead pra cada persona
        self._is_running = True
        self.key_lock = threading.Lock()
        
        # Carrega pool de APIs gratuitas anti-429
        self.api_keys = []
        groq = os.getenv("GROQ_API_KEY")
        if groq: self.api_keys.append({"provider": "groq", "key": groq, "model": "llama-3.3-71b-versatile"})
        
        for i in range(1, 6):
            gemini = os.getenv(f"GEMINI_KEY_{i}")
            if gemini: self.api_keys.append({"provider": "gemini", "key": gemini, "model": "gemini-1.5-flash"}) # Deve ficar fixo em 1.5 Flash por estabilidade
            
        if not self.api_keys:
            self.api_keys.append({"provider": "ollama", "key": "none", "model": "phi3:mini"})
            
        self.current_key_idx = 0

    async def start_loop(self):
        """Loop infinito assincrono (Background)."""
        logger.info("[ORACLE] Slow Track iniciada. Personas acordadas.")
        
        while self._is_running:
            try:
                # O Oracle processa dados calmamente a cada 2 minutos
                # sem congelar as funcoes de execucao e WebSocket do bot.
                await self._evaluate_comite()
            except Exception as e:
                logger.error(f"[ORACLE] Erro no fluxo do comite: {e}")
            
            # Aguarda 15 minutos (900 segundos) para evitar bloqueios de 429 nas APIs gratuitas
            await asyncio.sleep(900)

    async def _evaluate_comite(self):
        loop = asyncio.get_running_loop()
        
        # Coletar contexto atual
        current_macro_risk = self.state.get("macro_risk", 0.5)
        
        # ==========================================
        # PERSONA A: O Pragmatista (Analise de numeros)
        # ==========================================
        # No futuro podera iterar sobre Open Interest (OI), CVD, e Funding direto da DataEngine
        prompt_pragmatico = f"""
        Como o 'Pragmatista', voce ignora noticias e foca em dados crus.
        O risco macro economico atual medido e de {current_macro_risk:.2f} (0 a 1).
        Hipotese: Estamos em risco para comprar cripto longo?
        Responda concisamente e finalize com 'SCORE:' variando de -1.0 (urso) a 1.0 (touro).
        """
        
        # ==========================================
        # PERSONA B: O Visionario (Manchetes e Narrativa)
        # ==========================================
        # Placeholder: Poderia se alimentar de feeds RSS nas proximas versoes
        prompt_visionario = """
        Como o 'Visionario', voce entende de narrativas macro e fluxo institucional de ETFs.
        Dada a estrutura politica e regulacao americana atual de IA e Cripto, descreva sua
        previsao para BTC e finalize com 'SCORE:' variando de -1.0 a 1.0.
        """

        # ==========================================
        # PERSONA C: O Cetico (Invalidador via Neo4J / Memoria)
        # ==========================================
        prompt_cetico = "Como 'O Cetico', voce sempre busca razoes para o bot NAO operar.\n"
        if self.memory:
            falhas = self.memory.get_recent_failures(limit=3)
            falhas_str = ". ".join([f"Falhamos por {f.get('cause', 'desconhecido')}" for f in falhas]) if falhas else "Nenhuma."
            prompt_cetico += f"Ultimas falhas do modelo no Neo4J: {falhas_str}.\n"
        else:
            prompt_cetico += "Avisos arquivados: Mercado instavel."
        prompt_cetico += "Baseado num pessimismo saudavel, responda e finalize dizendo 'SCORE: ' -1.0 a 1.0."

        # Executa as tres Personas em paralelo
        tasks = [
            loop.run_in_executor(self.executor, self._query_llm, prompt_pragmatico),
            loop.run_in_executor(self.executor, self._query_llm, prompt_visionario),
            loop.run_in_executor(self.executor, self._query_llm, prompt_cetico)
        ]
        
        results = await asyncio.gather(*tasks)

        # Tratar resultados
        scores = []
        for res in results:
            score = self._extract_score(res)
            scores.append(score)
            
        avg_score = sum(scores) / len(scores) if scores else 0.0

        sentiment = "Neutral"
        if avg_score > 0.2:
            sentiment = "Bullish"
        elif avg_score < -0.2:
            sentiment = "Bearish"
            
        confidence = min(0.95, abs(avg_score))
        multiplier = 1.0 + (avg_score * 0.5)  # Se bull, 1.X, se bear, reduz exposição

        # Atualiza o Estado Compartilhado DE FORMA ATOMICA/INSTANTANEA
        # O Bot Master apenas lerá este dicionario, sem saber quando ou como foi atualizado
        self.state["sentiment"] = sentiment
        self.state["confidence"] = confidence
        self.state["multiplier"] = multiplier
        self.state["last_oracle_update"] = datetime.now().strftime('%H:%M:%S')

    def _query_llm(self, prompt: str) -> str:
        """Chamada bloqueante isolada por executor thread com Failover e Rotacao."""
        max_attempts = len(self.api_keys) * 2 if self.api_keys else 1
        attempts = 0
        
        while attempts < max_attempts:
            with self.key_lock:
                provider_info = self.api_keys[self.current_key_idx]
            
            provider = provider_info["provider"]
            api_key = provider_info["key"]
            model = provider_info["model"]
            
            try:
                if provider == "groq":
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
                    res = requests.post(url, headers=headers, json=payload, timeout=30)
                    
                    if res.status_code == 200:
                        return res.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                    elif res.status_code == 429:
                        logger.warning(f"[ORACLE] Groq Rate Limit (429). Trocando chave...")
                    else:
                        logger.warning(f"[ORACLE] Erro Groq: {res.status_code} - {res.text[:100]}")

                elif provider == "gemini":
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                    headers = {"Content-Type": "application/json"}
                    payload = {"contents": [{"parts": [{"text": prompt}]}]}
                    res = requests.post(url, headers=headers, json=payload, timeout=30)
                    
                    if res.status_code == 200:
                        candidates = res.json().get('candidates', [])
                        if candidates and 'content' in candidates[0]:
                            return candidates[0]['content'].get('parts', [{}])[0].get('text', '')
                        return ""
                    elif res.status_code == 429:
                        logger.warning(f"[ORACLE] Gemini Rate Limit (429). Trocando chave...")
                    else:
                        logger.warning(f"[ORACLE] Erro Gemini: {res.status_code} - {res.text[:100]}")
                
                else:
                    url = os.getenv("OLLAMA_URL", "http://ollama:11434/api/generate")
                    payload = {"model": model, "prompt": prompt, "stream": False}
                    res = requests.post(url, json=payload, timeout=40)
                    if res.status_code == 200:
                        return res.json().get("response", "")

            except Exception as e:
                logger.debug(f"[ORACLE] Erro de conexao API: {e}")
            
            # Se falhou, rotaciona a chave de forma sincronizada
            with self.key_lock:
                self.current_key_idx = (self.current_key_idx + 1) % len(self.api_keys)
            attempts += 1
            time.sleep(1)

        logger.error("[ORACLE] Todas as chaves falharam (limite ou erro).")
        return ""

    def _extract_score(self, text: str) -> float:
        """Isola a definicao numerica gerada pelo LLM ('SCORE: 0.8')."""
        if not text:
            return 0.0
        try:
            upp = text.upper()
            if "SCORE:" in upp:
                pieces = upp.split("SCORE:")
                val_str = pieces[-1].strip().split()[0]
                return max(-1.0, min(1.0, float(val_str.replace("'", "").replace('"', ''))))
        except Exception:
            pass
        return 0.0

    def stop(self):
        self._is_running = False
