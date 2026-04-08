# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import os
import logging
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Silenciar warnings verbosos do Neo4j sobre schema
logging.getLogger("neo4j").setLevel(logging.ERROR)
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)

load_dotenv()

class MarketMemory:
    """
    Memoria de Mercado via Neo4j (Grafo).
    Armazena e recupera a relacao entre Eventos Macro e Reacoes de Preco.
    Inspirado na arquitetura de agentes 'Long-term Memory' do @redamon.
    """

    def __init__(self):
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "password")
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self._verify_connection()
            self._initialize_schema()
        except Exception as e:
            print(f"[MEMORY] Falha ao conectar ao Neo4j: {e}")
            self.driver = None

    def _verify_connection(self):
        with self.driver.session() as session:
            session.run("RETURN 1")

    def _initialize_schema(self):
        """
        Garante que os Labels e Relationships existam no banco para evitar warnings.
        Cria e remove um conjunto minimo de dados.
        """
        if not self.driver: return
        query = """
        MERGE (e:Event {id: 'schema_seed'})
        MERGE (m:MacroState {id: 'schema_seed'})
        MERGE (d:Decision {id: 'schema_seed'})
        MERGE (o:Outcome {id: 'schema_seed'})
        MERGE (fs:FailedState {id: 'schema_seed'})
        MERGE (e)-[:HAPPENED_IN]->(m)
        MERGE (d)-[:BASED_ON]->(e)
        MERGE (o)-[:FOLLOWED]->(d)
        WITH e, m, d, o, fs
        DETACH DELETE e, m, d, o, fs
        """
        try:
            with self.driver.session() as session:
                session.run(query)
                print("[MEMORY] Schema inicializado (Neo4j).")
        except Exception as e:
            print(f"[MEMORY] Aviso ao inicializar schema: {e}")

    def close(self):
        if self.driver:
            self.driver.close()

    def record_context_and_decision(self, news_sentiment: float, macro_risk: float, decision: str):
        """
        Cria um snapshot do contexto atual e da decisao tomada.
        """
        if not self.driver: return
        
        timestamp = datetime.now().isoformat()
        
        # Cypher: Cria nos de Evento, Macro e Decisao com vinculos
        query = """
        CREATE (e:Event {sentiment: $sentiment, timestamp: $ts})
        CREATE (m:MacroState {risk_score: $risk, timestamp: $ts})
        CREATE (d:Decision {action: $action, timestamp: $ts})
        MERGE (e)-[:HAPPENED_IN]->(m)
        MERGE (d)-[:BASED_ON]->(e)
        RETURN elementId(d) as decision_id
        """
        try:
            with self.driver.session() as session:
                session.run(query, sentiment=news_sentiment, risk=macro_risk, action=decision, ts=timestamp)
        except Exception as e:
            print(f"[MEMORY] Erro ao gravar contexto: {e}")

    def get_historical_conviction(self, current_sentiment: float, current_risk: float, tolerance: float = 0.2):
        """
        Consulta o Grafo por situacoes similares e retorna o PnL medio.
        """
        if not self.driver: return 0.5 # Neutro 
        
        query = """
        MATCH (e:Event)-[:HAPPENED_IN]->(m:MacroState)
        WHERE abs(e.sentiment - $sent) < $tol AND abs(m.risk_score - $risk) < $tol
        MATCH (d:Decision)-[:BASED_ON]->(e)
        OPTIONAL MATCH (o:Outcome)-[:FOLLOWED]->(d)
        WITH d, o WHERE o IS NULL OR o["pnl"] IS NOT NULL
        RETURN avg(o["pnl"]) as avg_pnl, count(d) as total_occurrences
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, sent=current_sentiment, risk=current_risk, tol=tolerance).single()
                if result and result["total_occurrences"] > 0:
                    avg_pnl = result["avg_pnl"] or 0.0
                    return 0.5 + (avg_pnl * 5.0) # Normaliza PnL para Conviction Score
                return 0.5
        except Exception as e:
            print(f"[MEMORY] Erro ao consultar historico: {e}")
            return 0.5

    def record_outcome(self, pnl: float):
        """
        Vincula o resultado financeiro a ultima decisao tomada.
        """
        if not self.driver: return
        
        query = """
        MATCH (d:Decision)
        WHERE NOT (d)<-[:FOLLOWED]-(:Outcome)
        WITH d ORDER BY d.timestamp DESC LIMIT 1
        CREATE (o:Outcome {pnl: $pnl, timestamp: $ts})
        MERGE (o)-[:FOLLOWED]->(d)
        """
        try:
            with self.driver.session() as session:
                session.run(query, pnl=pnl, ts=datetime.now().isoformat())
        except Exception as e:
            print(f"[MEMORY] Erro ao gravar resultado: {e}")

    def record_market_state(self, symbol: str, price: float, sentiment: float):
        """
        Registra especificamente o preco e sentimento atual para uso futuro de Machine Learning.
        Garante que sempre tenhamos o snapshot temporal do MiroFish perfeitamente alinhado com OHLCV.
        """
        if not self.driver: return
        
        timestamp = datetime.now().isoformat()
        
        # Cypher: Cria no de MarketState puro (Preco + Setimento da AI)
        query = """
        CREATE (ms:MarketStateML {
            symbol: $symbol,
            price: $price,
            sentiment: $sentiment,
            timestamp: $ts,
            date: date()
        })
        RETURN elementId(ms)
        """
        try:
            with self.driver.session() as session:
                session.run(query, symbol=symbol, price=price, sentiment=sentiment, ts=timestamp)
        except Exception as e:
            print(f"[MEMORY] Erro ao gravar MarketState: {e}")

    def get_ancestral_dnas(self, vol: float, trend: float, sentiment: float, limit: int = 2):
        """
        Busca DNAs no histórico que tiveram alta performance em regimes similares.
        """
        if not self.driver: return []
        
        # Query Cypher: Busca por proximidade de Volatilidade e Tendencia
        query = """
        MATCH (r:Regime)-[:OPTIMAL_DNA]->(d:DNA)
        WHERE abs(r.volatility - $vol) < 0.005 AND abs(r.trend - $trend) < 0.05
        RETURN d.params as params, d.fitness as fitness, d.id as id
        ORDER BY d.fitness DESC
        LIMIT $limit
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, vol=vol, trend=trend, limit=limit)
                return [record["params"] for record in result]
        except Exception as e:
            print(f"[MEMORY] Erro ao buscar DNA ancestral: {e}")
            return []

    def record_failed_state(self, metrics: dict, cause: str):
        """Registra no grafo um cenário onde o bot falhou."""
        if not self.driver: return
        query = """
        CREATE (fs:FailedState {
            volatility: $vol,
            trend: $trend,
            sentiment: $sent,
            cause: $cause,
            timestamp: datetime()
        })
        """
        try:
            with self.driver.session() as session:
                session.run(query, vol=metrics.get('vol', 0), trend=metrics.get('trend', 0), 
                            sent=metrics.get('sent', 0), cause=cause)
        except Exception as e:
            print(f"[MEMORY] Erro ao gravar falha: {e}")

    def check_failure_risk(self, vol: float, trend: float, sentiment: float):
        """Busca se o estado atual é similar a falhas recentes."""
        if not self.driver: return 0.0
        query = """
        MATCH (fs:FailedState)
        WHERE abs(fs.volatility - $vol) < 0.003 AND abs(fs.trend - $trend) < 0.03
        RETURN count(fs) as failure_count
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, vol=vol, trend=trend).single()
                return result["failure_count"] if result else 0
        except Exception as e:
            print(f"[MEMORY] Erro ao checar risco de falha: {e}")
            return 0

    def get_recent_failures(self, limit: int = 10):
        """Busca as ultimas falhas registradas no grafo."""
        if not self.driver: return []
        query = "MATCH (fs:FailedState) RETURN fs ORDER BY fs.timestamp DESC LIMIT $limit"
        try:
            with self.driver.session() as session:
                result = session.run(query, limit=limit)
                return [record["fs"] for record in result]
        except Exception as e:
            print(f"[MEMORY] Erro ao buscar falhas: {e}")
            return []

if __name__ == "__main__":
    memory = MarketMemory()
    # Teste de gravacao
    memory.record_context_and_decision(0.8, 0.4, "APPROVE")
    # Teste de consulta
    conv = memory.get_historical_conviction(0.75, 0.45)
    print(f"Historical Conviction: {conv:.2f}")
    memory.close()
