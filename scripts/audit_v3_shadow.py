import os
from neo4j import GraphDatabase
from prettytable import PrettyTable

class ShadowAuditor:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def run_audit(self):
        print("\n" + "="*50)
        print("🔍 AUDITORIA DE PERFORMANCE: v3-Alpha (Shadow Mode)")
        print("="*50 + "\n")
        
        with self.driver.session() as session:
            self._audit_execution_funnel(session)
            self._audit_precision_metrics(session)

    def _audit_execution_funnel(self, session):
        """Mede o volume de sinais e a taxa de Veto do Oráculo de Imbalance."""
        query = """
        MATCH (d:Decision)
        WHERE d.reason CONTAINS 'v3-Alpha' OR d.reason CONTAINS 'Breakout'
        WITH count(d) as total_signals,
             sum(CASE WHEN d.status = 'VETOED' THEN 1 ELSE 0 END) as vetoed_signals,
             sum(CASE WHEN d.status = 'APPROVED' THEN 1 ELSE 0 END) as approved_signals
        RETURN total_signals, vetoed_signals, approved_signals
        """
        result = session.run(query).single()
        if not result:
            print("📊 FUNIL DE EXECUÇÃO: Nenhum sinal registrado no Neo4j.")
            return

        total = result["total_signals"] or 0
        vetoed = result["vetoed_signals"] or 0
        approved = result["approved_signals"] or 0
        
        veto_rate = (vetoed / total * 100) if total > 0 else 0
        
        print("📊 FUNIL DE EXECUÇÃO (Gatekeeper)")
        print(f"Total de Sinais v3 Gerados: {total}")
        print(f"Sinais Aprovados (Shadow):  {approved}")
        print(f"Sinais Vetados (Imbalance): {vetoed} ({veto_rate:.1f}% Veto Rate)\n")

    def _audit_precision_metrics(self, session):
        """Calcula o Hit Rate real (Precision) cruzando Entradas com Outcomes."""
        query = """
        MATCH (d:Decision)-[:RESULTOU_EM]->(o:Outcome)
        WHERE d.reason CONTAINS 'v3-Alpha' AND d.status = 'APPROVED'
        WITH count(o) as settled_trades,
             sum(CASE WHEN o.win = true THEN 1 ELSE 0 END) as winning_trades,
             sum(CASE WHEN o.win = false THEN 1 ELSE 0 END) as losing_trades,
             avg(o.pnl) as avg_pnl
        RETURN settled_trades, winning_trades, losing_trades, avg_pnl
        """
        result = session.run(query).single()
        if not result or result["settled_trades"] == 0:
            print("🎯 MÉTRICAS DE PRECISÃO: Nenhum trade liquidado ainda.")
            return

        settled = result["settled_trades"] or 0
        wins = result["winning_trades"] or 0
        losses = result["losing_trades"] or 0
        avg_pnl = result["avg_pnl"] or 0.0
        
        precision = (wins / settled * 100) if settled > 0 else 0
        
        table = PrettyTable()
        table.field_names = ["Métrica", "Valor"]
        table.align["Métrica"] = "l"
        table.align["Valor"] = "r"
        
        table.add_row(["Trades Liquidados (4h Horizon)", settled])
        table.add_row(["Ganhos (True Positives)", wins])
        table.add_row(["Perdas (False Positives)", losses])
        table.add_row(["", ""])
        table.add_row(["PRECISION (Hit Rate Real)", f"{precision:.2f}%"])
        table.add_row(["PnL Médio por Trade", f"{avg_pnl:.4f}%"])

        print("🎯 MÉTRICAS DE PRECISÃO DIRETA (Liquidada)")
        print(table)
        
        if settled > 0:
            print("\n[DIAGNÓSTICO]")
            if precision >= 35.0:
                print("🟢 SUCESSO: A Precision em tempo real superou o baseline. O Alpha foi validado.")
            elif precision >= 28.0:
                print("🟡 ALERTA: Precision aceitável, mas na zona de empate estatístico. Requer Payoff alto.")
            else:
                print("🔴 FALHA: Precision colapsou no mundo real. Possível Data Leakage residual no Sandbox.")

if __name__ == "__main__":
    # Carregar variáveis de ambiente (Neo4j Credentials)
    URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USER = os.getenv("NEO4J_USER", "neo4j")
    PASSWORD = os.getenv("NEO4J_PASSWORD", "password") # Ajuste conforme necessário
    
    auditor = ShadowAuditor(URI, USER, PASSWORD)
    try:
        auditor.run_audit()
    except Exception as e:
        print(f"[-] Erro na auditoria: {e}")
    finally:
        auditor.close()
