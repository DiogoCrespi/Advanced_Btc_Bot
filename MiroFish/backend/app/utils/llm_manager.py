# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
"""
Gerenciador de Chaves LLM (Rodizio e Failover)
Suporta OpenAI (Groq) e Google GenAI (Gemini)
"""

import os
import json
import time
import logging
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI
from google import genai
from ..config import Config

logger = logging.getLogger(__name__)

class LLMKeyManager:
    """Gerenciador de chaves com failover e cooldown"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMKeyManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self.state_file = os.path.join(os.path.dirname(__file__), '../data/key_pool_status.json')
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        
        # Pool de chaves (Prioridade: Groq -> Gemini 1..4)
        self.keys = [
            {"provider": "groq", "key": os.environ.get("GROQ_API_KEY"), "model": "llama-3.1-8b-instant", "base_url": "https://api.groq.com/openai/v1"},
            {"provider": "gemini", "key": os.environ.get("GEMINI_KEY_1"), "model": "gemini-3-flash-preview"},
            {"provider": "gemini", "key": os.environ.get("GEMINI_KEY_2"), "model": "gemini-3-flash-preview"},
            {"provider": "gemini", "key": os.environ.get("GEMINI_KEY_3"), "model": "gemini-3-flash-preview"},
            {"provider": "gemini", "key": os.environ.get("GEMINI_KEY_4"), "model": "gemini-3-flash-preview"},
        ]
        
        self.cooldowns = self._load_state()
        self._initialized = True

    def _load_state(self) -> Dict[str, float]:
        """Carrega o estado de cooldown das chaves"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Erro ao carregar estado das chaves: {e}")
        return {}

    def _save_state(self):
        """Salva o estado de cooldown"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.cooldowns, f)
        except Exception as e:
            logger.error(f"Erro ao salvar estado das chaves: {e}")

    def get_active_key(self) -> Optional[Dict[str, Any]]:
        """Busca a primeira chave que nao esteja em cooldown"""
        current_time = time.time()
        for i, k in enumerate(self.keys):
            key_id = f"key_{i}"
            cooldown_until = self.cooldowns.get(key_id, 0)
            
            if current_time > cooldown_until:
                return {**k, "id": key_id}
        return None

    def mark_as_exhausted(self, key_id: str):
        """Marca uma chave como exaurida por 24 horas"""
        # Reset as 00:00 do dia seguinte seria ideal, mas 24h resolve
        self.cooldowns[key_id] = time.time() + (24 * 3600)
        self._save_state()
        logger.warning(f"[LLM_MANAGER] Chave {key_id} marcada como exaurida por 24h.")

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4096) -> str:
        """Tenta realizar o chat usando as chaves do pool em cascata"""
        
        for _ in range(len(self.keys)):
            active_config = self.get_active_key()
            if not active_config:
                logger.error("[LLM_MANAGER] Todas as chaves estao exauridas!")
                return "Erro: Todas as APIs exauridas."

            try:
                if active_config["provider"] == "groq":
                    client = OpenAI(api_key=active_config["key"], base_url=active_config["base_url"])
                    response = client.chat.completions.create(
                        model=active_config["model"],
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    content = response.choices[0].message.content
                    return re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
                
                elif active_config["provider"] == "gemini":
                    client = genai.Client(api_key=active_config["key"])
                    # Converte mensagens para formato Gemini
                    prompt = self._format_messages_for_gemini(messages)
                    response = client.models.generate_content(
                        model=active_config["model"],
                        contents=prompt
                    )
                    return response.text.strip()
            
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "resource_exhausted" in error_msg or "quota" in error_msg:
                    logger.warning(f"[LLM_MANAGER] Rate limit atingido na chave {active_config['id']}. Pulando...")
                    self.mark_as_exhausted(active_config["id"])
                    continue
                else:
                    logger.error(f"[LLM_MANAGER] Erro inesperado na chave {active_config['id']}: {e}")
                    raise e
        
        return "Erro: Falha apos tentar todas as chaves."

    def _format_messages_for_gemini(self, messages: List[Dict[str, str]]) -> str:
        """Converte historico de mensagens em um prompt linear para Gemini (simplificado)"""
        formatted = ""
        for msg in messages:
            role = "System" if msg["role"] == "system" else "User" if msg["role"] == "user" else "Assistant"
            formatted += f"{role}: {msg['content']}\n\n"
        return formatted
