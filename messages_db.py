import sqlite3

DATABASE = 'users.db'


def init_messages_table():
    conn = sqlite3.connect(DATABASE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (sender_id) REFERENCES users(id),
            FOREIGN KEY (receiver_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()


def send_message(sender_id, receiver_id, content):
    conn = sqlite3.connect(DATABASE)
    conn.execute(
        'INSERT INTO messages (sender_id, receiver_id, content) VALUES (?, ?, ?)',
        (sender_id, receiver_id, content)
    )
    conn.commit()
    conn.close()


def get_conversation(user1_id, user2_id, limit=200):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
        SELECT * FROM messages
        WHERE (sender_id = ? AND receiver_id = ?)
           OR (sender_id = ? AND receiver_id = ?)
        ORDER BY created_at ASC
        LIMIT ?
    ''', (user1_id, user2_id, user2_id, user1_id, limit)).fetchall()
    conn.close()
    return rows


def mark_as_read(receiver_id, sender_id):
    conn = sqlite3.connect(DATABASE)
    conn.execute(
        'UPDATE messages SET is_read = 1 WHERE receiver_id = ? AND sender_id = ?',
        (receiver_id, sender_id)
    )
    conn.commit()
    conn.close()


def get_dialogs(user_id):
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
        SELECT
            u.id AS other_id,
            u.username AS other_username,
            u.avatar AS other_avatar,
            (SELECT content FROM messages m
             WHERE (m.sender_id = ? AND m.receiver_id = u.id)
                OR (m.sender_id = u.id AND m.receiver_id = ?)
             ORDER BY m.created_at DESC LIMIT 1) AS last_message,
            (SELECT created_at FROM messages m
             WHERE (m.sender_id = ? AND m.receiver_id = u.id)
                OR (m.sender_id = u.id AND m.receiver_id = ?)
             ORDER BY m.created_at DESC LIMIT 1) AS last_time,
            (SELECT COUNT(*) FROM messages m
             WHERE m.sender_id = u.id AND m.receiver_id = ? AND m.is_read = 0) AS unread
        FROM users u
        WHERE u.id != ?
          AND EXISTS (
              SELECT 1 FROM messages m
              WHERE (m.sender_id = ? AND m.receiver_id = u.id)
                 OR (m.sender_id = u.id AND m.receiver_id = ?)
          )
        ORDER BY last_time DESC
    ''', (user_id, user_id, user_id, user_id, user_id, user_id,
          user_id, user_id)).fetchall()
    conn.close()
    return rows


def count_unread_total(user_id):
    conn = sqlite3.connect(DATABASE)
    row = conn.execute(
        'SELECT COUNT(*) AS c FROM messages WHERE receiver_id = ? AND is_read = 0',
        (user_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else 0
