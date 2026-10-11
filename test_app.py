"""
Автотесты безопасности для Aura.
Запуск:  python test_app.py
"""
import os
import sys

os.environ['AURA_SECRET_KEY'] = 'test-secret-key-for-tests-only'

import app as app_module
from app import app, generate_password_hash, init_db, get_db, login_limiter
from flask import render_template_string


PASSED = 0
FAILED = 0
ERRORS = []


def ok(name):
    global PASSED
    PASSED += 1
    print(f'  \033[92m✅ PASS\033[0m  {name}')


def fail(name, reason):
    global FAILED
    FAILED += 1
    ERRORS.append((name, reason))
    print(f'  \033[91m❌ FAIL\033[0m  {name}')
    print(f'         \033[90m→ {reason}\033[0m')


def section(title):
    print(f'\n\033[96m▶ {title}\033[0m')


# ============================================================
# НАСТРОЙКА
# ============================================================
TEST_DB = 'test_users.db'
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

app_module.DATABASE = TEST_DB
app.config['TESTING'] = True

with app.app_context():
    init_db()
    db = get_db()
    db.execute(
        'INSERT INTO users (username, password_hash) VALUES (?, ?)',
        ('testuser', generate_password_hash('TestPass123'))
    )
    db.commit()


def get_csrf(client):
    client.get('/login')
    with client.session_transaction() as sess:
        return sess.get('_csrf', '')


def login(client, username='testuser', password='TestPass123'):
    csrf = get_csrf(client)
    return client.post('/login', data={
        'username': username,
        'password': password,
        '_csrf': csrf,
    }, follow_redirects=False)


# ============================================================
# ТЕСТ 1: SQL-инъекция
# ============================================================
section('ТЕСТ 1: SQL-инъекция в логине')

client = app.test_client()
payloads = [
    "admin' OR '1'='1",
    "' OR 1=1 --",
    "admin'--",
    "'; DROP TABLE users; --",
]

sql_ok = True
for payload in payloads:
    csrf = get_csrf(client)
    res = client.post('/login', data={
        'username': payload,
        'password': 'anything',
        '_csrf': csrf,
    }, follow_redirects=False)

    location = res.headers.get('Location', '')
    if res.status_code == 302 and '/feed' in location:
        fail('SQL-инъекция', f'Логин прошёл с payload: {payload}')
        sql_ok = False
        break

if sql_ok:
    with app.app_context():
        db = get_db()
        count = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        if count >= 1:
            ok('SQL-инъекция не проходит, таблица цела')
        else:
            fail('SQL-инъекция', 'Таблица users удалена!')


# ============================================================
# ТЕСТ 2: CSRF
# ============================================================
section('ТЕСТ 2: CSRF защита')

client = app.test_client()
login(client)

res = client.post('/feed', data={
    'content': 'Пост без CSRF'
}, follow_redirects=False)

if res.status_code == 403:
    ok('CSRF блокирует POST без токена (403)')
else:
    fail('CSRF', f'Ожидали 403, получили {res.status_code}')


# ============================================================
# ТЕСТ 3: Rate limit
# ============================================================
section('ТЕСТ 3: Rate limit (5 попыток)')

login_limiter.data.clear()

client = app.test_client()
blocked = False
for i in range(6):
    csrf = get_csrf(client)
    res = client.post('/login', data={
        'username': 'testuser',
        'password': 'WrongPassword',
        '_csrf': csrf,
    }, follow_redirects=True)
    body = res.get_data(as_text=True)
    if 'Слишком много' in body or 'Подождите' in body:
        ok(f'Rate limit сработал на попытке {i+1}')
        blocked = True
        break

if not blocked:
    fail('Rate limit', 'Блокировка не сработала за 6 попыток')


# ============================================================
# ТЕСТ 4: Чужой пост
# ============================================================
section('ТЕСТ 4: Удаление чужого поста')

with app.app_context():
    db = get_db()
    db.execute(
        'INSERT INTO users (username, password_hash) VALUES (?, ?)',
        ('victim', generate_password_hash('VictimPass123'))
    )
    db.commit()
    victim = db.execute(
        'SELECT id FROM users WHERE username = ?', ('victim',)
    ).fetchone()
    db.execute(
        'INSERT INTO posts (user_id, content) VALUES (?, ?)',
        (victim['id'], 'Пост жертвы')
    )
    db.commit()
    post = db.execute(
        'SELECT id FROM posts WHERE user_id = ?', (victim['id'],)
    ).fetchone()
    post_id = post['id']

login_limiter.data.clear()
client = app.test_client()
login(client)

with client.session_transaction() as sess:
    csrf = sess.get('_csrf', '')

client.post(f'/post/{post_id}/delete', data={
    '_csrf': csrf,
}, follow_redirects=True)

with app.app_context():
    db = get_db()
    still_there = db.execute(
        'SELECT id FROM posts WHERE id = ?', (post_id,)
    ).fetchone()

if still_there is not None:
    ok('Чужой пост не удалось удалить')
else:
    fail('Защита постов', 'Чужой пост был удалён!')


# ============================================================
# ТЕСТ 5: XSS
# ============================================================
section('ТЕСТ 5: XSS экранируется')

xss_payload = '<script>alert("XSS")</script>'

# Проверяем через тестовый HTTP-запрос (внутри request context)
client = app.test_client()

# Простой маршрут не нужен — используем test_request_context
with app.test_request_context('/'):
    from flask import render_template_string
    html = render_template_string('{{ content }}', content=xss_payload)

    if '<script>' in html and 'alert' in html:
        fail('XSS', f'Jinja НЕ экранирует: {html}')
    elif '&lt;script&gt;' in html:
        ok('Jinja autoescape экранирует HTML — XSS не пройдёт')
    else:
        fail('XSS', f'Неожиданный вывод: {html}')

    # Проверяем фильтр highlight
    html2 = render_template_string('{{ content|highlight }}', content=xss_payload)

    if '<script>' in html2 and 'alert' in html2:
        fail('XSS в highlight', f'Фильтр highlight уязвим')
    else:
        ok('Фильтр highlight тоже экранирует XSS')

# ============================================================
# ИТОГИ
# ============================================================
print('\n' + '=' * 55)
print(f'\033[96mИТОГО:\033[0m  \033[92m✅ {PASSED} passed\033[0m   \033[91m❌ {FAILED} failed\033[0m')
print('=' * 55)

if ERRORS:
    print('\n\033[91mОшибки:\033[0m')
    for name, reason in ERRORS:
        print(f'  • {name}: {reason}')

if os.path.exists(TEST_DB):
    try:
        os.remove(TEST_DB)
    except OSError:
        pass

sys.exit(1 if FAILED > 0 else 0)