import sqlite3
import os

def check_trades():
    db_path = "results/bot_ledger.db"
    if not os.path.exists(db_path):
        print(f"[-] Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check for active positions
    print("--- ACTIVE POSITIONS ---")
    cursor.execute("SELECT * FROM active_positions")
    positions = cursor.fetchall()
    for pos in positions:
        print(pos)
    
    # Check for completed shadow trades
    print("\n--- COMPLETED SHADOW TRADES ---")
    try:
        cursor.execute("SELECT * FROM trade_history WHERE is_shadow = 1")
        trades = cursor.fetchall()
        for trade in trades:
            print(trade)
        if not trades:
            print("No completed shadow trades found.")
    except Exception as e:
        print(f"Error: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_trades()
