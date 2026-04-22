# NOTA: Prints, logs e comentarios devem ser mantidos sem acentuacao para evitar quebra de encoding no Putty/Docker.
import os
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

class FeatureStore:
    """
    Persistent Feature Store using Parquet (pyarrow).
    Garante que o bot nao tenha 'cegueira de dados' apos reinicializacoes.
    """
    def __init__(self, data_dir="data", filename="market_history.parquet"):
        self.data_dir = data_dir
        self.filepath = os.path.join(data_dir, filename)
        os.makedirs(data_dir, exist_ok=True)

    def load_history(self):
        """
        Carrega o historico do disco.
        Usa memory-mapping (pyarrow) para performance multicore.
        """
        if not os.path.exists(self.filepath):
            print(f"[WARN] [STORE] Arquivo {self.filepath} nao encontrado.")
            return pd.DataFrame()
        
        try:
            # Memory mapping=True permite que multiplos processos leiam sem duplicar RAM excessivamente
            table = pq.read_table(self.filepath, memory_map=True)
            df = table.to_pandas()
            print(f"[SUCCESS] [STORE] Carregadas {len(df)} amostras do historico persistente.")
            return df
        except Exception as e:
            print(f"[ERROR] [STORE] Erro ao carregar Parquet: {e}")
            return pd.DataFrame()

    def save_history(self, df):
        """
        Salva (ou sobrescreve) o historico completo.
        """
        if df.empty: return
        
        try:
            table = pa.Table.from_pandas(df)
            pq.write_table(table, self.filepath, compression='snappy')
            # print(f"💾 [STORE] Historico persistido: {len(df)} linhas.")
        except Exception as e:
            print(f"[ERROR] [STORE] Erro ao salvar Parquet: {e}")

    def append_new_data(self, new_df):
        """
        Faz o append incremental para evitar re-escrita total (mais eficiente).
        """
        if new_df.empty: return
        
        try:
            if not os.path.exists(self.filepath):
                self.save_history(new_df)
                return

            # Para Parquet, append "real" exige abrir um Writer ou concatenar e salvar.
            # Como o dataset e relativamente pequeno (< 1GB), concatenar e o mais seguro para integridade.
            existing_df = self.load_history()
            
            # Garante que nao haja duplicatas por timestamp
            combined_df = pd.concat([existing_df, new_df]).sort_index()
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
            
            self.save_history(combined_df)
        except Exception as e:
            print(f"[ERROR] [STORE] Erro no append Parquet: {e}")

    def get_maturity_score(self, df):
        """
        Retorna um score de maturidade baseado no volume de dados.
        """
        count = len(df)
        if count == 0: return 0.0
        # 10.000 e o alvo de maturidade plena.
        return min(1.0, count / 10000)
