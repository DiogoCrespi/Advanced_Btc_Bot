from neo4j import GraphDatabase
import pandas as pd
import os

def export_market_memory():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    query = """
    MATCH (ms:MarketStateML)
    RETURN ms.timestamp AS timestamp, ms.price AS price, ms.sentiment AS sentiment, ms.symbol as symbol
    ORDER BY ms.timestamp ASC
    """
    
    with driver.session() as session:
        result = session.run(query)
        df = pd.DataFrame([dict(record) for record in result])
        
    if df.empty:
        print("[!] Nenhum dado encontrado no Neo4j. Certifique-se de que o bot gravou o MarketState.")
        return

    os.makedirs("data", exist_ok=True)
    out_path = "data/mirofish_sentiment_history.parquet"
    df.to_parquet(out_path, compression='snappy')
    print(f"[*] Exportado com sucesso: {len(df)} registros para '{out_path}'.")

if __name__ == "__main__":
    export_market_memory()
