import sqlite3
import time
import os
import json
import random

import sys
from unittest.mock import MagicMock

sys.modules['camel'] = MagicMock()
sys.modules['camel.models'] = MagicMock()
sys.modules['camel.types'] = MagicMock()
sys.modules['oasis'] = MagicMock()

# Mock action logger dependencies
sys.modules['action_logger'] = MagicMock()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../MiroFish/backend')))
from scripts.run_parallel_simulation import fetch_new_actions_from_db

def create_mock_db(db_path, num_actions=1000):
    if os.path.exists(db_path):
        os.remove(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE user (user_id INTEGER PRIMARY KEY, agent_id INTEGER, name TEXT, user_name TEXT)''')
    cursor.execute('''CREATE TABLE post (post_id INTEGER PRIMARY KEY, user_id INTEGER, content TEXT, original_post_id INTEGER, quote_content TEXT)''')
    cursor.execute('''CREATE TABLE comment (comment_id INTEGER PRIMARY KEY, post_id INTEGER, user_id INTEGER, content TEXT)''')
    cursor.execute('''CREATE TABLE follow (follow_id INTEGER PRIMARY KEY, follower_id INTEGER, followee_id INTEGER)''')
    cursor.execute('''CREATE TABLE trace (user_id INTEGER, action TEXT, info TEXT, created_at TEXT)''')

    for i in range(1, 501):
        cursor.execute("INSERT INTO user VALUES (?, ?, ?, ?)", (i, i, f"Name{i}", f"User{i}"))

    for i in range(1, 2001):
        cursor.execute("INSERT INTO post VALUES (?, ?, ?, ?, ?)", (i, random.randint(1, 500), f"Post {i} content", random.choice([None, random.randint(1, 1000)]), f"Quote {i} content"))
        cursor.execute("INSERT INTO comment VALUES (?, ?, ?, ?)", (i, random.randint(1, 2000), random.randint(1, 500), f"Comment {i} content"))
        cursor.execute("INSERT INTO follow VALUES (?, ?, ?)", (i, random.randint(1, 500), random.randint(1, 500)))

    actions = ['like_post', 'dislike_post', 'repost', 'quote_post', 'follow', 'mute', 'like_comment', 'create_comment']
    for i in range(num_actions):
        action = random.choice(actions)
        info = {}
        if action in ('like_post', 'dislike_post', 'create_comment'):
            info['post_id'] = random.randint(1, 2000)
        elif action == 'repost':
            info['new_post_id'] = random.randint(1, 2000)
        elif action == 'quote_post':
            info['quoted_id'] = random.randint(1, 2000)
            info['new_post_id'] = random.randint(1, 2000)
        elif action == 'follow':
            info['follow_id'] = random.randint(1, 2000)
        elif action == 'mute':
            info['user_id'] = random.randint(1, 500)
        elif action in ('like_comment', 'dislike_comment'):
            info['comment_id'] = random.randint(1, 2000)

        cursor.execute("INSERT INTO trace VALUES (?, ?, ?, ?)", (random.randint(1, 500), action, json.dumps(info), "2023-01-01"))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    db_path = "test_perf.db"
    create_mock_db(db_path, 10000)

    agent_names = {i: f"AgentName_{i}" for i in range(1, 501)}

    start_time = time.time()
    actions, last_rowid = fetch_new_actions_from_db(db_path, 0, agent_names)
    duration = time.time() - start_time

    print(f"Fetched {len(actions)} actions in {duration:.4f} seconds")
