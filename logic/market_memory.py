# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import os
from datetime import datetime
from neo4j import GraphDatabase
from dotenv import load_dotenv

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
        MERGE (e)-[:HAPPENED_IN]->(m)
        MERGE (d)-[:BASED_ON]->(e)
        MERGE (o)-[:FOLLOWED]->(d)
        WITH e, m, d, o
        DETACH DELETE e, m, d, o
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

if __name__ == "__main__":
    memory = MarketMemory()
    # Teste de gravacao
    memory.record_context_and_decision(0.8, 0.4, "APPROVE")
    # Teste de consulta
    conv = memory.get_historical_conviction(0.75, 0.45)
    print(f"Historical Conviction: {conv:.2f}")
    memory.close()
