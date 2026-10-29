"""
Логи попыток входа и подозрительных действий.
Нужно для ограничения брутфорса и аудита.
"""
import sqlite3
from datetime import datetime

DATABASE = 'users.db'


def init_security_tables():
    try:
        conn = sqlite3.connect(DATABASE, timeout=10)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                ip TEXT,
                success INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS security_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                username TEXT,
                ip TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        print(f"⚠️ Ошибка инициализации таблиц безопасности: {e}")


def log_login(username, ip, success):
    """Безопасная запись попытки входа."""
    try:
        conn = sqlite3.connect(DATABASE, timeout=10)
        conn.execute(
            'INSERT INTO login_attempts (username, ip, success) VALUES (?, ?, ?)',
            (username, ip, 1 if success else 0)
        )
        conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        # Если база заблокирована — не роняем сервер
        print(f"⚠️ [LOGIN LOG ERROR] Не удалось записать попытку: {e}")


def count_failed_recent(username, ip, minutes=15):
    """Сколько неудачных попыток за последние N минут."""
    try:
        conn = sqlite3.connect(DATABASE, timeout=10)
        row = conn.execute('''
            SELECT COUNT(*) FROM login_attempts
            WHERE (username = ? OR ip = ?)
              AND success = 0
              AND created_at > datetime('now', ?)
        ''', (username, ip, f'-{minutes} minutes')).fetchone()
        conn.close()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


def log_security_event(event, username=None, ip=None, details=''):
    """Безопасная запись события безопасности."""
    try:
        conn = sqlite3.connect(DATABASE, timeout=10)
        conn.execute(
            'INSERT INTO security_log (event, username, ip, details) VALUES (?, ?, ?, ?)',
            (event, username, ip, details)
        )
        conn.commit()
        conn.close()
    except sqlite3.OperationalError as e:
        # Если БД перегружена — просто игнорируем, чтобы не вызвать каскадный отказ
        print(f"⚠️ [SECURITY LOG ERROR] Не удалось записать лог: {e}")
