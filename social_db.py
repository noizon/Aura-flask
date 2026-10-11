import sqlite3

DATABASE = 'users.db'

ALLOWED_EMOJIS = ['👍', '❤️', '😂', '🔥', '😮', '😢']


def init_social_tables():
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            UNIQUE(post_id, user_id, emoji)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def toggle_reaction(post_id, user_id, emoji):
    if emoji not in ALLOWED_EMOJIS:
        return False
    conn = sqlite3.connect(DATABASE)
    existing = conn.execute(
        'SELECT id FROM reactions WHERE post_id = ? AND user_id = ? AND emoji = ?',
        (post_id, user_id, emoji)
    ).fetchone()
    if existing:
        conn.execute('DELETE FROM reactions WHERE id = ?', (existing[0],))
    else:
        conn.execute(
            'INSERT INTO reactions (post_id, user_id, emoji) VALUES (?, ?, ?)',
            (post_id, user_id, emoji)
        )
    conn.commit()
    conn.close()
    return True


def get_reactions_for_post(post_id, user_id):
    conn = sqlite3.connect(DATABASE)
    rows = conn.execute('''
        SELECT emoji, COUNT(*) FROM reactions WHERE post_id = ? GROUP BY emoji
    ''', (post_id,)).fetchall()
    mine_rows = conn.execute('''
        SELECT emoji FROM reactions WHERE post_id = ? AND user_id = ?
    ''', (post_id, user_id)).fetchall()
    conn.close()
    return {
        'counts': {e: c for e, c in rows},
        'mine': [e for (e,) in mine_rows]
    }


def get_reactions_for_posts(post_ids, user_id):
    if not post_ids:
        return {}
    conn = sqlite3.connect(DATABASE)
    ph = ','.join('?' * len(post_ids))
    rows = conn.execute(f'''
        SELECT post_id, emoji, COUNT(*) FROM reactions
        WHERE post_id IN ({ph}) GROUP BY post_id, emoji
    ''', post_ids).fetchall()
    mine_rows = conn.execute(f'''
        SELECT post_id, emoji FROM reactions
        WHERE post_id IN ({ph}) AND user_id = ?
    ''', (*post_ids, user_id)).fetchall()
    conn.close()
    result = {pid: {'counts': {}, 'mine': []} for pid in post_ids}
    for pid, e, c in rows:
        result[pid]['counts'][e] = c
    for pid, e in mine_rows:
        result[pid]['mine'].append(e)
    return result


def add_comment(post_id, user_id, content):
    conn = sqlite3.connect(DATABASE)
    conn.execute(
        'INSERT INTO comments (post_id, user_id, content) VALUES (?, ?, ?)',
        (post_id, user_id, content)
    )
    conn.commit()
    conn.close()


def get_comments_for_post(post_id):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
        SELECT c.id, c.content, c.created_at, c.user_id,
               u.username, u.avatar
        FROM comments c JOIN users u ON u.id = c.user_id
        WHERE c.post_id = ? ORDER BY c.created_at ASC
    ''', (post_id,)).fetchall()
    conn.close()
    return rows


def count_comments_for_posts(post_ids):
    if not post_ids:
        return {}
    conn = sqlite3.connect(DATABASE)
    ph = ','.join('?' * len(post_ids))
    rows = conn.execute(f'''
        SELECT post_id, COUNT(*) FROM comments
        WHERE post_id IN ({ph}) GROUP BY post_id
    ''', post_ids).fetchall()
    conn.close()
    return {p: c for p, c in rows}
# ============================================================
# РЕАКЦИИ НА КОММЕНТАРИИ
# ============================================================
def init_comment_reactions_table():
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comment_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            UNIQUE(comment_id, user_id, emoji)
        )
    ''')
    conn.commit()
    conn.close()


def toggle_comment_reaction(comment_id, user_id, emoji):
    if emoji not in ALLOWED_EMOJIS:
        return False
    conn = sqlite3.connect(DATABASE)
    existing = conn.execute(
        'SELECT id FROM comment_reactions WHERE comment_id = ? AND user_id = ? AND emoji = ?',
        (comment_id, user_id, emoji)
    ).fetchone()
    if existing:
        conn.execute('DELETE FROM comment_reactions WHERE id = ?', (existing[0],))
    else:
        conn.execute(
            'INSERT INTO comment_reactions (comment_id, user_id, emoji) VALUES (?, ?, ?)',
            (comment_id, user_id, emoji)
        )
    conn.commit()
    conn.close()
    return True


def get_reactions_for_comments(comment_ids, user_id):
    if not comment_ids:
        return {}
    conn = sqlite3.connect(DATABASE)
    ph = ','.join('?' * len(comment_ids))
    rows = conn.execute(f'''
        SELECT comment_id, emoji, COUNT(*) FROM comment_reactions
        WHERE comment_id IN ({ph}) GROUP BY comment_id, emoji
    ''', comment_ids).fetchall()
    mine_rows = conn.execute(f'''
        SELECT comment_id, emoji FROM comment_reactions
        WHERE comment_id IN ({ph}) AND user_id = ?
    ''', (*comment_ids, user_id)).fetchall()
    conn.close()
    result = {cid: {'counts': {}, 'mine': []} for cid in comment_ids}
    for cid, e, c in rows:
        result[cid]['counts'][e] = c
    for cid, e in mine_rows:
        result[cid]['mine'].append(e)
    return result