import sqlite3

DATABASE = 'users.db'


def init_follows_table():
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS follows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            follower_id INTEGER NOT NULL,
            following_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(follower_id, following_id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            actor_id INTEGER,
            type TEXT NOT NULL,
            post_id INTEGER,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS saved_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            post_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, post_id)
        )
    ''')
    # Онлайн-статус
    cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
    if 'last_seen' not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN last_seen TIMESTAMP DEFAULT NULL")

    # Медиа в постах
    cols = [r[1] for r in conn.execute("PRAGMA table_info(posts)").fetchall()]
    if 'image' not in cols:
        conn.execute("ALTER TABLE posts ADD COLUMN image TEXT DEFAULT ''")

    conn.commit()
    conn.close()


# ---------- ПОДПИСКИ ----------
def toggle_follow(follower_id, following_id):
    if follower_id == following_id:
        return False
    conn = sqlite3.connect(DATABASE)
    ex = conn.execute(
        'SELECT id FROM follows WHERE follower_id = ? AND following_id = ?',
        (follower_id, following_id)
    ).fetchone()
    if ex:
        conn.execute('DELETE FROM follows WHERE id = ?', (ex[0],))
        conn.commit()
        conn.close()
        return 'unfollowed'
    else:
        conn.execute(
            'INSERT INTO follows (follower_id, following_id) VALUES (?, ?)',
            (follower_id, following_id)
        )
        conn.commit()
        conn.close()
        return 'followed'


def is_following(follower_id, following_id):
    conn = sqlite3.connect(DATABASE)
    row = conn.execute(
        'SELECT 1 FROM follows WHERE follower_id = ? AND following_id = ?',
        (follower_id, following_id)
    ).fetchone()
    conn.close()
    return bool(row)


def get_followers_count(user_id):
    conn = sqlite3.connect(DATABASE)
    row = conn.execute(
        'SELECT COUNT(*) FROM follows WHERE following_id = ?', (user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def get_following_count(user_id):
    conn = sqlite3.connect(DATABASE)
    row = conn.execute(
        'SELECT COUNT(*) FROM follows WHERE follower_id = ?', (user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def get_following_ids(user_id):
    conn = sqlite3.connect(DATABASE)
    rows = conn.execute(
        'SELECT following_id FROM follows WHERE follower_id = ?', (user_id,)
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ---------- УВЕДОМЛЕНИЯ ----------
def add_notification(user_id, actor_id, ntype, post_id=None):
    if user_id == actor_id:
        return
    conn = sqlite3.connect(DATABASE)
    conn.execute(
        'INSERT INTO notifications (user_id, actor_id, type, post_id) VALUES (?, ?, ?, ?)',
        (user_id, actor_id, ntype, post_id)
    )
    conn.commit()
    conn.close()


def get_notifications(user_id, limit=50):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
        SELECT n.*, u.username AS actor_username, u.avatar AS actor_avatar,
               (SELECT content FROM posts p WHERE p.id = n.post_id) AS post_content
        FROM notifications n
        LEFT JOIN users u ON u.id = n.actor_id
        WHERE n.user_id = ?
        ORDER BY n.created_at DESC
        LIMIT ?
    ''', (user_id, limit)).fetchall()
    conn.close()
    return rows


def count_unread_notifications(user_id):
    conn = sqlite3.connect(DATABASE)
    row = conn.execute(
        'SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0',
        (user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else 0


def mark_notifications_read(user_id):
    conn = sqlite3.connect(DATABASE)
    conn.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


# ---------- СОХРАНЁННЫЕ ПОСТЫ ----------
def toggle_save_post(user_id, post_id):
    conn = sqlite3.connect(DATABASE)
    ex = conn.execute(
        'SELECT id FROM saved_posts WHERE user_id = ? AND post_id = ?',
        (user_id, post_id)
    ).fetchone()
    if ex:
        conn.execute('DELETE FROM saved_posts WHERE id = ?', (ex[0],))
        result = False
    else:
        conn.execute(
            'INSERT INTO saved_posts (user_id, post_id) VALUES (?, ?)',
            (user_id, post_id)
        )
        result = True
    conn.commit()
    conn.close()
    return result


def get_saved_post_ids(user_id):
    conn = sqlite3.connect(DATABASE)
    rows = conn.execute(
        'SELECT post_id FROM saved_posts WHERE user_id = ?', (user_id,)
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


# ---------- ОНЛАЙН-СТАТУС ----------
def touch_last_seen(user_id):
    conn = sqlite3.connect(DATABASE)
    conn.execute(
        "UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (user_id,)
    )
    conn.commit()
    conn.close()