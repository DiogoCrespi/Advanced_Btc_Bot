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

def chunked_in_query(cursor, query_template: str, id_list: List[int], chunk_size: int = 900) -> List[Tuple]:
    results = []
    for i in range(0, len(id_list), chunk_size):
        chunk = id_list[i:i + chunk_size]
        placeholders = ','.join(['?'] * len(chunk))
        query = query_template.replace("IN_PLACEHOLDERS", placeholders)
        cursor.execute(query, chunk)
        results.extend(cursor.fetchall())
    return results

def fetch_new_actions_from_db_optimized(
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

        # ID collections for batch querying
        quote_post_ids = set()
        direct_post_ids = set()
        repost_new_post_ids = set()
        comment_ids = set()
        follow_ids = set()
        mute_user_ids = set()

        for rowid, user_id, action, info_json in cursor.fetchall():
            new_last_rowid = rowid

            if action in FILTERED_ACTIONS:
                continue

            try:
                action_args = json.loads(info_json) if info_json else {}
            except json.JSONDecodeError:
                action_args = {}

            simplified_args = {}
            if 'content' in action_args: simplified_args['content'] = action_args['content']
            if 'post_id' in action_args: simplified_args['post_id'] = action_args['post_id']
            if 'comment_id' in action_args: simplified_args['comment_id'] = action_args['comment_id']
            if 'quoted_id' in action_args: simplified_args['quoted_id'] = action_args['quoted_id']
            if 'new_post_id' in action_args: simplified_args['new_post_id'] = action_args['new_post_id']
            if 'follow_id' in action_args: simplified_args['follow_id'] = action_args['follow_id']
            if 'query' in action_args: simplified_args['query'] = action_args['query']
            if 'like_id' in action_args: simplified_args['like_id'] = action_args['like_id']
            if 'dislike_id' in action_args: simplified_args['dislike_id'] = action_args['dislike_id']
            # for mute
            if 'user_id' in action_args: simplified_args['user_id'] = action_args['user_id']
            if 'target_id' in action_args: simplified_args['target_id'] = action_args['target_id']

            action_type = ACTION_TYPE_MAP.get(action, action.upper())

            # Collect IDs for N+1 optimization
            if action_type in ('LIKE_POST', 'DISLIKE_POST', 'CREATE_COMMENT'):
                if 'post_id' in simplified_args: direct_post_ids.add(simplified_args['post_id'])
            elif action_type == 'REPOST':
                if 'new_post_id' in simplified_args: repost_new_post_ids.add(simplified_args['new_post_id'])
            elif action_type == 'QUOTE_POST':
                if 'quoted_id' in simplified_args: direct_post_ids.add(simplified_args['quoted_id'])
                if 'new_post_id' in simplified_args: quote_post_ids.add(simplified_args['new_post_id'])
            elif action_type == 'FOLLOW':
                if 'follow_id' in simplified_args: follow_ids.add(simplified_args['follow_id'])
            elif action_type == 'MUTE':
                target = simplified_args.get('user_id') or simplified_args.get('target_id')
                if target: mute_user_ids.add(target)
            elif action_type in ('LIKE_COMMENT', 'DISLIKE_COMMENT'):
                if 'comment_id' in simplified_args: comment_ids.add(simplified_args['comment_id'])

            raw_actions.append({
                'agent_id': user_id,
                'agent_name': agent_names.get(user_id, f'Agent_{user_id}'),
                'action_type': action_type,
                'action_args': simplified_args,
            })

        # --- BATCH FETCHING ---

        # 1. quote_contents_map
        quote_contents_map = {}
        if quote_post_ids:
            rows = chunked_in_query(cursor, "SELECT post_id, quote_content FROM post WHERE post_id IN (IN_PLACEHOLDERS)", list(quote_post_ids))
            for r in rows:
                if r[1]: quote_contents_map[r[0]] = r[1]

        # 2. repost original_post_ids
        repost_original_map = {}
        if repost_new_post_ids:
            rows = chunked_in_query(cursor, "SELECT post_id, original_post_id FROM post WHERE post_id IN (IN_PLACEHOLDERS)", list(repost_new_post_ids))
            for r in rows:
                if r[1]:
                    repost_original_map[r[0]] = r[1]
                    direct_post_ids.add(r[1])

        # 3. followee_ids
        followee_map = {}
        if follow_ids:
            rows = chunked_in_query(cursor, "SELECT follow_id, followee_id FROM follow WHERE follow_id IN (IN_PLACEHOLDERS)", list(follow_ids))
            for r in rows:
                if r[1]:
                    followee_map[r[0]] = r[1]
                    mute_user_ids.add(r[1]) # Add to user_ids to fetch

        # We will collect all user_ids that need resolving
        user_ids_to_fetch = set(mute_user_ids)

        # 4. posts
        post_raw_map = {}
        if direct_post_ids:
            rows = chunked_in_query(cursor, """
                SELECT p.post_id, p.content, p.user_id, u.agent_id
                FROM post p
                LEFT JOIN user u ON p.user_id = u.user_id
                WHERE p.post_id IN (IN_PLACEHOLDERS)
            """, list(direct_post_ids))
            for r in rows:
                post_raw_map[r[0]] = {'content': r[1], 'user_id': r[2], 'agent_id': r[3]}
                if r[2]: user_ids_to_fetch.add(r[2])

        # 5. comments
        comment_raw_map = {}
        if comment_ids:
            rows = chunked_in_query(cursor, """
                SELECT c.comment_id, c.content, c.user_id, u.agent_id
                FROM comment c
                LEFT JOIN user u ON c.user_id = u.user_id
                WHERE c.comment_id IN (IN_PLACEHOLDERS)
            """, list(comment_ids))
            for r in rows:
                comment_raw_map[r[0]] = {'content': r[1], 'user_id': r[2], 'agent_id': r[3]}
                if r[2]: user_ids_to_fetch.add(r[2])

        # 6. user names
        user_names_cache = {}
        if user_ids_to_fetch:
            rows = chunked_in_query(cursor, "SELECT user_id, agent_id, name, user_name FROM user WHERE user_id IN (IN_PLACEHOLDERS)", list(user_ids_to_fetch))
            for r in rows:
                uid, aid, name, uname = r
                if aid is not None and aid in agent_names:
                    user_names_cache[uid] = agent_names[aid]
                else:
                    user_names_cache[uid] = name or uname or ''

        # Helper to resolve author name
        def resolve_author_name(u_id, a_id):
            if a_id is not None and a_id in agent_names: return agent_names[a_id]
            if u_id: return user_names_cache.get(u_id, '')
            return ''

        post_info_cache = {}
        for pid, data in post_raw_map.items():
            post_info_cache[pid] = {
                'content': data['content'] or '',
                'author_name': resolve_author_name(data['user_id'], data['agent_id'])
            }

        comment_info_cache = {}
        for cid, data in comment_raw_map.items():
            comment_info_cache[cid] = {
                'content': data['content'] or '',
                'author_name': resolve_author_name(data['user_id'], data['agent_id'])
            }

        # --- ENRICHMENT (No DB Queries) ---
        for action_data in raw_actions:
            action_type = action_data['action_type']
            action_args = action_data['action_args']

            try:
                if action_type in ('LIKE_POST', 'DISLIKE_POST', 'CREATE_COMMENT'):
                    pid = action_args.get('post_id')
                    if pid and pid in post_info_cache:
                        action_args['post_content'] = post_info_cache[pid]['content']
                        action_args['post_author_name'] = post_info_cache[pid]['author_name']

                elif action_type == 'REPOST':
                    npid = action_args.get('new_post_id')
                    if npid and npid in repost_original_map:
                        orig_id = repost_original_map[npid]
                        if orig_id in post_info_cache:
                            action_args['original_content'] = post_info_cache[orig_id]['content']
                            action_args['original_author_name'] = post_info_cache[orig_id]['author_name']

                elif action_type == 'QUOTE_POST':
                    qid = action_args.get('quoted_id')
                    if qid and qid in post_info_cache:
                        action_args['original_content'] = post_info_cache[qid]['content']
                        action_args['original_author_name'] = post_info_cache[qid]['author_name']

                    npid = action_args.get('new_post_id')
                    if npid:
                        if npid in quote_contents_map:
                            action_args['quote_content'] = quote_contents_map[npid]

                elif action_type == 'FOLLOW':
                    fid = action_args.get('follow_id')
                    if fid and fid in followee_map:
                        target_id = followee_map[fid]
                        if target_id in user_names_cache:
                            action_args['target_user_name'] = user_names_cache[target_id]

                elif action_type == 'MUTE':
                    target = action_args.get('user_id') or action_args.get('target_id')
                    if target and target in user_names_cache:
                        action_args['target_user_name'] = user_names_cache[target]

                elif action_type in ('LIKE_COMMENT', 'DISLIKE_COMMENT'):
                    cid = action_args.get('comment_id')
                    if cid and cid in comment_info_cache:
                        action_args['comment_content'] = comment_info_cache[cid]['content']
                        action_args['comment_author_name'] = comment_info_cache[cid]['author_name']

            except Exception as e:
                print(f"Failed enrichment: {e}")

            actions.append(action_data)

        conn.close()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Failed to read db: {e}")

    return actions, new_last_rowid

if __name__ == "__main__":
    db_path = "test_perf.db"
    # create_mock_db(db_path, 10000)

    agent_names = {i: f"AgentName_{i}" for i in range(1, 501)}

    start_time = time.time()
    actions, last_rowid = fetch_new_actions_from_db_optimized(db_path, 0, agent_names)
    duration = time.time() - start_time

    print(f"Optimized Fetched {len(actions)} actions in {duration:.4f} seconds")
