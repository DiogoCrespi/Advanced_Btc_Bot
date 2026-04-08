import sqlite3
import time
from typing import Dict, Any, Optional
import json
import sys
import os
from unittest.mock import MagicMock

# Mock camel and oasis
sys.modules['camel'] = MagicMock()
sys.modules['camel.models'] = MagicMock()
sys.modules['camel.types'] = MagicMock()
sys.modules['oasis'] = MagicMock()
sys.modules['action_logger'] = MagicMock()

def create_mock_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user (
            user_id INTEGER PRIMARY KEY,
            agent_id INTEGER,
            name TEXT,
            user_name TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS post (
            post_id INTEGER PRIMARY KEY,
            content TEXT,
            user_id INTEGER,
            original_post_id INTEGER,
            quote_content TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trace (
            user_id INTEGER,
            action TEXT,
            info TEXT
        )
    """)

    # insert data
    for i in range(100):
        cursor.execute("INSERT INTO user (user_id, agent_id, name, user_name) VALUES (?, ?, ?, ?)",
                       (i, i, f"name_{i}", f"username_{i}"))

    for i in range(1000):
        cursor.execute("INSERT INTO post (post_id, content, user_id) VALUES (?, ?, ?)",
                       (i, f"content_{i}", i % 100))

    # Let's increase the number of traces to make the execution time more noticeable
    for i in range(50000):
        action = "like_post"
        info = json.dumps({"post_id": i % 1000}) # 1000 unique posts
        cursor.execute("INSERT INTO trace (user_id, action, info) VALUES (?, ?, ?)",
                       (i % 100, action, info))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    if os.path.exists("test_bench.db"):
        os.remove("test_bench.db")
    create_mock_db("test_bench.db")

    # import functions from MiroFish.backend.scripts.run_parallel_simulation
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'MiroFish/backend/scripts')))
    from run_parallel_simulation import fetch_new_actions_from_db

    agent_names = {i: f"Agent_{i}" for i in range(100)}

    start = time.time()
    actions, last_rowid = fetch_new_actions_from_db("test_bench.db", 0, agent_names)
    end = time.time()

    print(f"Baseline Time taken: {end - start:.4f} seconds")
    print(f"Fetched {len(actions)} actions")
