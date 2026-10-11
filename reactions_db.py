import sqlite3

DATABASE = 'users.db'

ALLOWED_EMOJIS = ['👍', '❤️', '😂', '🔥', '😮', '😢']


def init_reactions_table():
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            emoji TEXT NOT NULL,
            UNIQUE(post_id, user_id, emoji),
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()


def toggle_reaction(post_id, user_id, emoji):
    """Если реакция есть — удаляем, если нет — добавляем."""
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


def get_reactions_for_posts(post_ids, user_id):
    """
    Возвращает dict: {post_id: {'counts': {emoji: count}, 'mine': set(emoji)}}
    """
    if not post_ids:
        return {}

    conn = sqlite3.connect(DATABASE)
    placeholders = ','.join('?' * len(post_ids))

    rows = conn.execute(f'''
        SELECT post_id, emoji, COUNT(*) AS c
        FROM reactions
        WHERE post_id IN ({placeholders})
        GROUP BY post_id, emoji
    ''', post_ids).fetchall()

    mine_rows = conn.execute(f'''
        SELECT post_id, emoji
        FROM reactions
        WHERE post_id IN ({placeholders}) AND user_id = ?
    ''', (*post_ids, user_id)).fetchall()

    conn.close()

    result = {pid: {'counts': {}, 'mine': set()} for pid in post_ids}

    for post_id, emoji, count in rows:
        result[post_id]['counts'][emoji] = count

    for post_id, emoji in mine_rows:
        result[post_id]['mine'].add(emoji)

    return result