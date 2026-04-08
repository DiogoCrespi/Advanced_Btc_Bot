import sqlite3

def check_schema(db_path):
    print(f"Schema for {db_path}:")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(post)")
        for col in cursor.fetchall():
            print(col)
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

check_schema('MiroFish/backend/scripts/twitter_simulation.db')
check_schema('MiroFish/backend/scripts/reddit_simulation.db')
