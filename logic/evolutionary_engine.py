import numpy as np
import random
import hashlib
import json
from datetime import datetime

class DNA:
    """
    Representação genética dos parâmetros operacionais do Bot.
    Engloba ML, Rotulação e Risco.
    """
    def __init__(self, params=None):
        if params:
            self.params = params
        else:
            # DNA Padrão (Indivíduo Alfa Original)
            self.params = {
                # Genes de Cognição (ML)
                "n_estimators": 200,
                "max_depth": 12,
                "min_samples_leaf": 10,
                
                # Genes de Rotulação (Triple Barrier)
                "tp": 0.015,
                "sl": 0.008,
                "horizon": 24,
                
                # Genes de Convicção e Risco
                "min_confidence": 0.55,
                "risk_per_trade": 0.05,
                "trailing_stop": 0.005
            }
        self.fitness = 0.0
        self.trades = [] # Histórico de trades virtuais (PnL)
        self.id = hashlib.md5(json.dumps(self.params, sort_keys=True).encode()).hexdigest()[:8]

    def mutate(self, rate=0.10):
        """Aplica mutação aleatória nos genes."""
        new_params = self.params.copy()
        for key in new_params:
            if isinstance(new_params[key], (int, float)):
                # Variação gaussiana baseada na taxa de mutação
                variation = np.random.normal(0, new_params[key] * rate)
                new_params[key] += variation
                
                # Constraints e Tipagem
                if key in ["n_estimators", "max_depth", "min_samples_leaf", "horizon"]:
                    new_params[key] = max(5, int(round(new_params[key])))
                elif key == "min_confidence":
                    new_params[key] = clip(new_params[key], 0.35, 0.95)
                else:
                    new_params[key] = max(0.001, new_params[key])
        return DNA(new_params)

def clip(val, vmin, vmax):
    return max(vmin, min(val, vmax))

class EvolutionaryEngine:
    """
    Motor de Seleção Natural que gerencia a população de Shadow Models.
    """
    def __init__(self, population_size=5):
        self.population_size = population_size
        self.population = [DNA() for _ in range(population_size)]
        self.generation = 0
        self.failures = [] # Lista de FailedStates sincronizada do Neo4j
        
        # Inicia com o Indivíduo Alfa
        self.alfa = DNA()
        self.population.append(self.alfa)
        
        # Gera descendentes mutantes iniciais
        for _ in range(population_size - 1):
            self.population.append(self.alfa.mutate(rate=0.20))

    def evaluate_fitness(self, dna, market_context=None):
        """
        Calcula a aptidão: (ROI * WinRate) - MaxDrawdown.
        """
        if not dna.trades:
            return 0.0
        
        pnls = dna.trades
        roi = sum(pnls)
        win_rate = len([p for p in pnls if p > 0]) / len(pnls) if pnls else 0
        
        # Max Drawdown Simples
        cum_pnl = np.cumsum(pnls)
        peak = np.maximum.accumulate(cum_pnl)
        drawdown = np.max(peak - cum_pnl) if len(cum_pnl) > 0 else 0
        
        # Função de Aptidão Final
        dna.fitness = (roi * win_rate) - (drawdown * 1.5)
        return dna.fitness

    def evolve(self):
        """Ciclo de Seleção, Crossover e Mutação."""
        # 1. Ranking por Fitness
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        print(f"[EVOLUTION] Geração {self.generation} | Melhor Fitness: {self.population[0].fitness:.4f}")
        
        # 2. Seleção de Elite (Top 2 sobreviveram)
        elite = self.population[:2]
        new_population = [elite[0], elite[1]]
        
        # 3. Crossover (Mistura de genes entre os top 2)
        while len(new_population) < self.population_size:
            child_params = {}
            parent_a, parent_b = elite[0].params, elite[1].params
            for key in parent_a:
                child_params[key] = random.choice([parent_a[key], parent_b[key]])
            
            child = DNA(child_params)
            
            # 4. Mutação Progressiva
            if random.random() < 0.3:
                child = child.mutate(rate=0.05)
                
            new_population.append(child)
            
        self.population = new_population
        self.generation += 1
        return self.population[0] # Retorna o novo provável Alfa

    def inject_immigrants(self, dna_params_list):
        """Injeta DNAs ancestrais na população (substituindo os piores)."""
        if not dna_params_list:
            return
        
        # Ordena para identificar os piores
        self.population.sort(key=lambda x: x.fitness)
        
        injected_count = 0
        for params_json in dna_params_list:
            if injected_count >= 2: break # Limite de injeção por ciclo
            
            # Converter de JSON str se necessário (Neo4j as vezes retorna como string)
            params = params_json if isinstance(params_json, dict) else json.loads(params_json)
            
            new_dna = DNA(params)
            print(f"[EVOLUTION] Injetando Imigrante Ancestral {new_dna.id}")
            self.population[injected_count] = new_dna
            injected_count += 1

    def sync_failures(self, failed_metrics_list):
        """Sincroniza os estados de falha para aplicar o 'Anti-Gene'."""
        self.failures = failed_metrics_list

    def evaluate_fitness(self, dna):
        """Calcula fitness baseada em trades reais/virtuais e penaliza Anti-Genes."""
        if not dna.trades:
            dna.fitness = 0.0
            return
            
        win_rate = len([t for t in dna.trades if t > 0]) / len(dna.trades)
        roi = sum(dna.trades)
        
        # Penalidade Anti-Gene: Se o DNA for muito similar a falhas recentes
        penalty = 0.0
        for f in self.failures:
             # Simplificacao: Penaliza se o DNA for alpha em regimes falhos
             penalty += 0.05
             
        dna.fitness = (roi * win_rate) - penalty
