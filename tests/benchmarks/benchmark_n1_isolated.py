import sqlite3
import time
import os
import json
import random
from typing import Dict, Any, List, Optional, Tuple

# Mocking parts of run_parallel_simulation

FILTERED_ACTIONS = {'refresh', 'sign_up'}

ACTION_TYPE_MAP = {
    'create_post': 'CREATE_POST',
    'like_post': 'LIKE_POST',
    'dislike_post': 'DISLIKE_POST',
    'repost': 'REPOST',
    'quote_post': 'QUOTE_POST',
    'follow': 'FOLLOW',
    'mute': 'MUTE',
    'create_comment': 'CREATE_COMMENT',
    'like_comment': 'LIKE_COMMENT',
    'dislike_comment': 'DISLIKE_COMMENT',
    'search_posts': 'SEARCH_POSTS',
    'search_user': 'SEARCH_USER',
    'trend': 'TREND',
    'do_nothing': 'DO_NOTHING',
    'interview': 'INTERVIEW',
}

def _get_user_name(
    cursor,
    user_id: int,
    agent_names: Dict[int, str],
    user_names_cache: Optional[Dict[int, str]] = None
) -> Optional[str]:
    if user_names_cache is not None and user_id in user_names_cache:
        return user_names_cache[user_id]

    try:
        cursor.execute("""
            SELECT agent_id, name, user_name FROM user WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            agent_id = row[0]
            name = row[1]
            user_name = row[2]

            if agent_id is not None and agent_id in agent_names:
                result = agent_names[agent_id]
            else:
                result = name or user_name or ''

            if user_names_cache is not None:
                user_names_cache[user_id] = result
            return result
    except Exception:
        pass

    if user_names_cache is not None:
        user_names_cache[user_id] = None
    return None

def _get_post_info(
    cursor,
    post_id: int,
    agent_names: Dict[int, str],
    user_names_cache: Optional[Dict[int, str]] = None
) -> Optional[Dict[str, str]]:
    try:
        cursor.execute("""
            SELECT p.content, p.user_id, u.agent_id
            FROM post p
            LEFT JOIN user u ON p.user_id = u.user_id
            WHERE p.post_id = ?
        """, (post_id,))
        row = cursor.fetchone()
        if row:
            content = row[0] or ''
            user_id = row[1]
            agent_id = row[2]

            author_name = ''
            if agent_id is not None and agent_id in agent_names:
                author_name = agent_names[agent_id]
            elif user_id:
                author_name = _get_user_name(cursor, user_id, agent_names, user_names_cache) or ''

            return {'content': content, 'author_name': author_name}
    except Exception:
        pass
    return None

def _get_comment_info(
    cursor,
    comment_id: int,
    agent_names: Dict[int, str],
    user_names_cache: Optional[Dict[int, str]] = None
) -> Optional[Dict[str, str]]:
    try:
        cursor.execute("""
            SELECT c.content, c.user_id, u.agent_id
            FROM comment c
            LEFT JOIN user u ON c.user_id = u.user_id
            WHERE c.comment_id = ?
        """, (comment_id,))
        row = cursor.fetchone()
        if row:
            content = row[0] or ''
            user_id = row[1]
            agent_id = row[2]

            author_name = ''
            if agent_id is not None and agent_id in agent_names:
                author_name = agent_names[agent_id]
            elif user_id:
                author_name = _get_user_name(cursor, user_id, agent_names, user_names_cache) or ''

            return {'content': content, 'author_name': author_name}
    except Exception:
        pass
    return None

def _enrich_action_context(
    cursor,
    action_type: str,
    action_args: Dict[str, Any],
    agent_names: Dict[int, str],
    quote_contents_map: Optional[Dict[int, str]] = None,
    user_names_cache: Optional[Dict[int, str]] = None
) -> None:
    try:
        if action_type in ('LIKE_POST', 'DISLIKE_POST'):
            post_id = action_args.get('post_id')
            if post_id:
                post_info = _get_post_info(cursor, post_id, agent_names, user_names_cache)
                if post_info:
                    action_args['post_content'] = post_info.get('content', '')
                    action_args['post_author_name'] = post_info.get('author_name', '')

        elif action_type == 'REPOST':
            new_post_id = action_args.get('new_post_id')
            if new_post_id:
                cursor.execute("""
                    SELECT original_post_id FROM post WHERE post_id = ?
                """, (new_post_id,))
                row = cursor.fetchone()
                if row and row[0]:
                    original_post_id = row[0]
                    original_info = _get_post_info(cursor, original_post_id, agent_names, user_names_cache)
                    if original_info:
                        action_args['original_content'] = original_info.get('content', '')
                        action_args['original_author_name'] = original_info.get('author_name', '')

        elif action_type == 'QUOTE_POST':
            quoted_id = action_args.get('quoted_id')
            new_post_id = action_args.get('new_post_id')

            if quoted_id:
                original_info = _get_post_info(cursor, quoted_id, agent_names, user_names_cache)
                if original_info:
                    action_args['original_content'] = original_info.get('content', '')
                    action_args['original_author_name'] = original_info.get('author_name', '')

            if new_post_id:
                if quote_contents_map is not None and new_post_id in quote_contents_map:
                    action_args['quote_content'] = quote_contents_map[new_post_id]
                elif quote_contents_map is None:
                    cursor.execute("""
                        SELECT quote_content FROM post WHERE post_id = ?
                    """, (new_post_id,))
                    row = cursor.fetchone()
                    if row and row[0]:
                        action_args['quote_content'] = row[0]

        elif action_type == 'FOLLOW':
            follow_id = action_args.get('follow_id')
            if follow_id:
                cursor.execute("""
                    SELECT followee_id FROM follow WHERE follow_id = ?
                """, (follow_id,))
                row = cursor.fetchone()
                if row:
                    followee_id = row[0]
                    target_name = _get_user_name(cursor, followee_id, agent_names, user_names_cache)
                    if target_name:
                        action_args['target_user_name'] = target_name

        elif action_type == 'MUTE':
            target_id = action_args.get('user_id') or action_args.get('target_id')
            if target_id:
                target_name = _get_user_name(cursor, target_id, agent_names, user_names_cache)
                if target_name:
                    action_args['target_user_name'] = target_name

        elif action_type in ('LIKE_COMMENT', 'DISLIKE_COMMENT'):
            comment_id = action_args.get('comment_id')
            if comment_id:
                comment_info = _get_comment_info(cursor, comment_id, agent_names, user_names_cache)
                if comment_info:
                    action_args['comment_content'] = comment_info.get('content', '')
                    action_args['comment_author_name'] = comment_info.get('author_name', '')

        elif action_type == 'CREATE_COMMENT':
            post_id = action_args.get('post_id')
            if post_id:
                post_info = _get_post_info(cursor, post_id, agent_names, user_names_cache)
                if post_info:
                    action_args['post_content'] = post_info.get('content', '')
                    action_args['post_author_name'] = post_info.get('author_name', '')

    except Exception as e:
        print(f"Failed enrichment: {e}")

def fetch_new_actions_from_db(
    db_path: str,
    last_rowid: int,
    agent_names: Dict[int, str]
) -> Tuple[List[Dict[str, Any]], int]:
    actions = []
    new_last_rowid = last_rowid

    if not os.path.exists(db_path):
        return actions, new_last_rowid

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT rowid, user_id, action, info
            FROM trace
            WHERE rowid > ?
            ORDER BY rowid ASC
        """, (last_rowid,))

        raw_actions = []
        quote_post_ids = set()

        for rowid, user_id, action, info_json in cursor.fetchall():
            new_last_rowid = rowid

            if action in FILTERED_ACTIONS:
                continue

            try:
                action_args = json.loads(info_json) if info_json else {}
            except json.JSONDecodeError:
                action_args = {}

            simplified_args = {}
            if 'content' in action_args:
                simplified_args['content'] = action_args['content']
            if 'post_id' in action_args:
                simplified_args['post_id'] = action_args['post_id']
            if 'comment_id' in action_args:
                simplified_args['comment_id'] = action_args['comment_id']
            if 'quoted_id' in action_args:
                simplified_args['quoted_id'] = action_args['quoted_id']
            if 'new_post_id' in action_args:
                simplified_args['new_post_id'] = action_args['new_post_id']
            if 'follow_id' in action_args:
                simplified_args['follow_id'] = action_args['follow_id']
            if 'query' in action_args:
                simplified_args['query'] = action_args['query']
            if 'like_id' in action_args:
                simplified_args['like_id'] = action_args['like_id']
            if 'dislike_id' in action_args:
                simplified_args['dislike_id'] = action_args['dislike_id']

            action_type = ACTION_TYPE_MAP.get(action, action.upper())

            if action_type == 'QUOTE_POST':
                new_post_id = simplified_args.get('new_post_id')
                if new_post_id:
                    quote_post_ids.add(new_post_id)

            raw_actions.append({
                'agent_id': user_id,
                'agent_name': agent_names.get(user_id, f'Agent_{user_id}'),
                'action_type': action_type,
                'action_args': simplified_args,
            })

        quote_contents_map = {}
        if quote_post_ids:
            chunk_size = 900
            quote_post_ids_list = list(quote_post_ids)
            for i in range(0, len(quote_post_ids_list), chunk_size):
                chunk = quote_post_ids_list[i:i + chunk_size]
                placeholders = ','.join(['?'] * len(chunk))
                cursor.execute(f"""
                    SELECT post_id, quote_content FROM post WHERE post_id IN ({placeholders})
                """, chunk)
                for row in cursor.fetchall():
                    if row[1]:
                        quote_contents_map[row[0]] = row[1]

        user_names_cache = {}
        for action_data in raw_actions:
            _enrich_action_context(cursor, action_data['action_type'], action_data['action_args'], agent_names, quote_contents_map, user_names_cache)

            actions.append(action_data)

        conn.close()
    except Exception as e:
        print(f"Failed to read db: {e}")

    return actions, new_last_rowid

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
