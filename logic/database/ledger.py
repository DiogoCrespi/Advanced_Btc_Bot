import sqlite3
import os
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger("Ledger")

class Ledger:
    """
    Financial Ledger using SQLite for ACID-compliant persistence of 
    balance, active positions, and trade history.
    """
    def __init__(self, db_path: str = "results/bot_ledger.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_db()

    def _initialize_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Table for Balance History
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS balance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    balance REAL,
                    total_equity REAL,
                    reason TEXT
                )
            """)
            # Table for Active Positions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS active_positions (
                    asset TEXT PRIMARY KEY,
                    entry_price REAL,
                    signal INTEGER,
                    qty REAL,
                    cost REAL,
                    timestamp DATETIME,
                    order_id TEXT
                )
            """)
            # Table for Completed Trades
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asset TEXT,
                    side TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    qty REAL,
                    pnl_pct REAL,
                    pnl_nominal REAL,
                    entry_time DATETIME,
                    exit_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                    reason TEXT
                )
            """)
            conn.commit()

    def save_balance(self, balance: float, total_equity: float, reason: str = "UPDATE"):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO balance_history (balance, total_equity, reason) VALUES (?, ?, ?)",
                    (balance, total_equity, reason)
                )
        except Exception as e:
            logger.error(f"Error saving balance to SQLite: {e}")

    def get_last_balance(self) -> Optional[float]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                res = conn.execute("SELECT balance FROM balance_history ORDER BY id DESC LIMIT 1").fetchone()
                return res[0] if res else None
        except Exception:
            return None

    def update_position(self, asset: str, data: Optional[Dict[str, Any]]):
        """If data is None, the position is closed (deleted)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                if data is None:
                    conn.execute("DELETE FROM active_positions WHERE asset = ?", (asset,))
                else:
                    conn.execute("""
                        INSERT OR REPLACE INTO active_positions 
                        (asset, entry_price, signal, qty, cost, timestamp, order_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        asset, data['entry'], data['signal'], data['qty'], 
                        data['cost'], data['time'], data.get('order_id')
                    ))
        except Exception as e:
            logger.error(f"Error updating position for {asset}: {e}")

    def load_active_positions(self) -> Dict[str, List[Dict[str, Any]]]:
        positions = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("SELECT * FROM active_positions").fetchall()
                for r in rows:
                    asset = r[0]
                    positions[asset] = [{
                        "entry": r[1],
                        "signal": r[2],
                        "qty": r[3],
                        "cost": r[4],
                        "time": r[5],
                        "order_id": r[6]
                    }]
        except Exception as e:
            logger.error(f"Error loading positions: {e}")
        return positions

    def record_completed_trade(self, asset: str, side: str, entry: float, exit: float, qty: float, pnl_pct: float, pnl_nominal: float, entry_time: str, reason: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO trade_history 
                    (asset, side, entry_price, exit_price, qty, pnl_pct, pnl_nominal, entry_time, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (asset, side, entry, exit, qty, pnl_pct, pnl_nominal, entry_time, reason))
        except Exception as e:
            logger.error(f"Error recording completed trade: {e}")

    def get_recent_performance(self, limit: int = 20) -> Dict[str, Any]:
        """Calculates accuracy and total PnL from the last N trades."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                trades = conn.execute(
                    "SELECT pnl_pct FROM trade_history ORDER BY id DESC LIMIT ?", 
                    (limit,)
                ).fetchall()
                
                if not trades:
                    return {"accuracy": 0.5, "total_pnl": 0.0, "count": 0}
                
                wins = len([t for t in trades if t['pnl_pct'] > 0])
                acc = wins / len(trades)
                total_pnl = sum([t['pnl_pct'] for t in trades])
                
                return {
                    "accuracy": acc,
                    "total_pnl": total_pnl,
                    "count": len(trades)
                }
        except Exception as e:
            logger.error(f"Error getting performance: {e}")
            return {"accuracy": 0.5, "total_pnl": 0.0, "count": 0}
