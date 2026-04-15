# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import threading
import time
import os
import psutil
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger("Watchdog")

class Watchdog(threading.Thread):
    """
    Agente de Monitoramento (Cão de Guarda).
    Roda em uma thread separada para monitorar a saude do bot sem bloquear o loop principal.
    """
    def __init__(self, bot):
        super().__init__(daemon=True)
        self.bot = bot
        self.name = "HealthWatchdog"
        self._is_running = True
        
        # Thresholds
        self.latency_threshold_ms = 500  # 0.5 segundos (Alerta)
        self.critical_latency_ms = 2000  # 2.0 segundos (Safe Mode)
        self.ram_threshold_pct = 85.0    # 85% de uso (Safe Mode)
        self.heartbeat_threshold_sec = 120 # 2 minutos sem tick (Critical)

        self.last_latency = 0
        self.last_ram = 0
        self.neo4j_ok = True

    def run(self):
        print(f"[WATCHDOG] Iniciado em thread separada (ID: {self.ident})")
        while self._is_running:
            try:
                # 1. Verificar RAM do Sistema
                self._check_ram()
                
                # 2. Verificar Latência da API (Binance)
                self._check_latency()
                
                # 3. Verificar Conexão Neo4j
                self._check_neo4j()
                
                # 4. Verificar Heartbeat do Bot
                self._check_heartbeat()
                
                # Reportar Saúde
                self._report_health()
                
            except Exception as e:
                print(f"[WATCHDOG] Erro no loop de monitoramento: {e}")
            
            time.sleep(30) # Monitoramento a cada 30 segundos

    def stop(self):
        self._is_running = False

    def _check_ram(self):
        mem = psutil.virtual_memory()
        self.last_ram = mem.percent
        if self.last_ram > self.ram_threshold_pct:
            msg = f"❗ ALERTA: Uso de RAM crítico ({self.last_ram}%)! Ativando Safe Mode."
            print(f"[WATCHDOG] {msg}")
            self.bot.safe_mode = True
            self.bot.notify_telegram(msg, title="WATCHDOG CRITICAL")

    def _check_latency(self):
        # Como o Watchdog roda em Thread, precisamos de um mini-loop async se quisermos usar o AsyncClient.
        # Simplificação: Usar um ping simples ou uma requisição requests cronometrada para evitar conflitos de loop.
        import requests
        try:
            start = time.time()
            requests.get("https://api.binance.com/api/v3/ping", timeout=5)
            self.last_latency = int((time.time() - start) * 1000)
            
            if self.last_latency > self.critical_latency_ms:
                self.bot.safe_mode = True
                self.bot.notify_telegram(f"📉 Latência Crítica: {self.last_latency}ms! Safe Mode ATIVO.", title="WATCHDOG CRITICAL")
            elif self.last_latency > self.latency_threshold_ms:
                self.bot.notify_telegram(f"⚠️ Latência Alta: {self.last_latency}ms.", title="WATCHDOG WARNING")
        except Exception as e:
            self.last_latency = 9999
            print(f"[WATCHDOG] Falha ao verificar latência: {e}")

    def _check_neo4j(self):
        if not self.bot.memory or not self.bot.memory.driver:
            self.neo4j_ok = False
            return
        
        try:
            with self.bot.memory.driver.session() as session:
                session.run("RETURN 1").single()
            self.neo4j_ok = True
        except Exception:
            self.neo4j_ok = False
            msg = "🔌 Erro de conexão com Neo4j detectado!"
            print(f"[WATCHDOG] {msg}")
            # Não ativa safe_mode por padrão para o Neo4j (opcional)

    def _check_heartbeat(self):
        # Verifica se o bot mestre atualizou o timestamp do último ciclo
        last_tick = getattr(self.bot, 'last_tick', 0)
        if last_tick == 0: return # Bot ainda inicializando
        
        diff = time.time() - last_tick
        if diff > self.heartbeat_threshold_sec:
            msg = f"💀 HEARTBEAT FAIL: Bot principal não responde há {int(diff)}s!"
            print(f"[WATCHDOG] {msg}")
            self.bot.notify_telegram(msg, title="WATCHDOG CRITICAL")
            # Aqui poderíamos tentar reiniciar o serviço via comando OS se necessário

    def _report_health(self):
        status = "OK" if not self.bot.safe_mode else "SAFE_MODE"
        neo_status = "UP" if self.neo4j_ok else "DOWN"
        # Log silencioso que aparece apenas no console a cada ciclo
        print(f"[WATCHDOG] Health: {status} | Latency: {self.last_latency}ms | RAM: {self.last_ram}% | Neo4j: {neo_status}")
