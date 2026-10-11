import os
import re
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from uuid import uuid4
from flask import (
    Flask, render_template, redirect, url_for,
    request, flash, session, g, jsonify, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

from messages_db import (
    init_messages_table, send_message, get_conversation,
    mark_as_read, get_dialogs, count_unread_total
)
from social_db import (
    init_social_tables, toggle_reaction, get_reactions_for_post,
    get_reactions_for_posts, add_comment, get_comments_for_post,
    count_comments_for_posts, ALLOWED_EMOJIS
)
from follow_db import (
    init_follows_table, toggle_follow, is_following,
    get_followers_count, get_following_count, get_following_ids,
    add_notification, get_notifications, count_unread_notifications,
    mark_notifications_read, toggle_save_post, get_saved_post_ids,
    touch_last_seen
)
from security import (
    generate_csrf_token, check_password_strength, validate_upload,
    RateLimiter, is_safe_redirect_url, short_hash
)
from security_db import (
    init_security_tables, log_login, count_failed_recent,
    log_security_event
)

# ============================================================
# КОНФИГ
# ============================================================
app = Flask(__name__)

SECRET_FILE = '.secret_key'
if os.environ.get('AURA_SECRET_KEY'):
    app.config['SECRET_KEY'] = os.environ['AURA_SECRET_KEY']
elif os.path.exists(SECRET_FILE):
    with open(SECRET_FILE, 'r') as f:
        app.config['SECRET_KEY'] = f.read().strip()
else:
    import secrets
    key = secrets.token_hex(32)
    with open(SECRET_FILE, 'w') as f:
        f.write(key)
    app.config['SECRET_KEY'] = key

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

app.config['UPLOAD_FOLDER'] = os.path.join('static', 'avatars')
app.config['POST_MEDIA_FOLDER'] = os.path.join('static', 'posts')
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

DATABASE = 'users.db'

login_limiter = RateLimiter(max_attempts=5, window_seconds=15 * 60)
register_limiter = RateLimiter(max_attempts=3, window_seconds=60 * 60)
post_limiter = RateLimiter(max_attempts=10, window_seconds=60)
comment_limiter = RateLimiter(max_attempts=20, window_seconds=60)


# ============================================================
# ПЕРЕВОДЫ (RU / EN)
# ============================================================
TRANSLATIONS = {
    'ru': {
        'feed': 'Лента',
        'trends': 'Тренды',
        'chats': 'Чаты',
        'notifications': 'Уведомления',
        'saved': 'Сохранённые',
        'profile': 'Профиль',
        'logout': 'Выйти',
        'login': 'Войти',
        'register': 'Регистрация',
        'search_placeholder': 'Поиск людей...',
        'whats_new': 'Что у вас нового?',
        'publish': 'Опубликовать',
        'photo': 'Фото',
        'for_you': 'Для вас',
        'following': 'Подписки',
        'no_posts': 'Пока постов нет',
        'delete': 'Удалить',
        'edit_profile': 'Редактировать профиль',
        'subscribe': 'Подписаться',
        'unsubscribe': 'Отписаться',
        'write': 'Написать',
        'name': 'Имя',
        'age': 'Возраст',
        'city': 'Город',
        'about': 'О себе',
        'posts': 'постов',
        'followers': 'подписчиков',
        'following_count': 'подписок',
        'repost': 'Репост',
        'views': 'Просмотры',
        'comments': 'Комментарии',
        'language': 'Язык',
        'save': 'Сохранить',
        'cancel': 'Отмена',
        'my_profile': 'Мой профиль',
        'admin_panel': 'Админ-панель',
        'users': 'Пользователей',
        'messages': 'Сообщений',
        'blocked': 'Забанено',
        'muted': 'В муте',
        'mute': 'Мут',
        'unmute': 'Размут',
        'ban': 'Бан',
        'unban': 'Разбан',
        'security_log': 'Лог безопасности',
        'recent_events': 'Последние события',
        'this_is_you': 'это ты',
        'send': 'Отправить',
        'message_placeholder': 'Сообщение...',
        'comment_placeholder': 'Написать комментарий...',
        'no_comments': 'Комментариев нет',
        'no_dialogs': 'Диалогов нет',
        'no_notifications': 'Уведомлений нет',
        'no_saved': 'Вы пока ничего не сохранили',
        'trends_title': 'Самые популярные хэштеги',
        'no_tags': 'Пока нет хэштегов. Напиши пост с #тегом!',
        'login_title': 'Вход',
        'register_title': 'Регистрация',
        'login_placeholder': 'Логин',
        'password_placeholder': 'Пароль',
        'confirm_placeholder': 'Повторите пароль',
        'no_account': 'Нет аккаунта?',
        'have_account': 'Уже есть аккаунт?',
        'current_lang': 'Текущий язык: Русский',
    },
    'en': {
        'feed': 'Feed',
        'trends': 'Trends',
        'chats': 'Chats',
        'notifications': 'Notifications',
        'saved': 'Saved',
        'profile': 'Profile',
        'logout': 'Log out',
        'login': 'Log in',
        'register': 'Sign up',
        'search_placeholder': 'Search people...',
        'whats_new': "What's new?",
        'publish': 'Publish',
        'photo': 'Photo',
        'for_you': 'For you',
        'following': 'Following',
        'no_posts': 'No posts yet',
        'delete': 'Delete',
        'edit_profile': 'Edit profile',
        'subscribe': 'Follow',
        'unsubscribe': 'Unfollow',
        'write': 'Message',
        'name': 'Name',
        'age': 'Age',
        'city': 'City',
        'about': 'About',
        'posts': 'posts',
        'followers': 'followers',
        'following_count': 'following',
        'repost': 'Repost',
        'views': 'Views',
        'comments': 'Comments',
        'language': 'Language',
        'save': 'Save',
        'cancel': 'Cancel',
        'my_profile': 'My profile',
        'admin_panel': 'Admin panel',
        'users': 'Users',
        'messages': 'Messages',
        'blocked': 'Blocked',
        'muted': 'Muted',
        'mute': 'Mute',
        'unmute': 'Unmute',
        'ban': 'Ban',
        'unban': 'Unban',
        'security_log': 'Security log',
        'recent_events': 'Recent events',
        'this_is_you': 'this is you',
        'send': 'Send',
        'message_placeholder': 'Message...',
        'comment_placeholder': 'Write a comment...',
        'no_comments': 'No comments',
        'no_dialogs': 'No dialogs',
        'no_notifications': 'No notifications',
        'no_saved': "You haven't saved anything yet",
        'trends_title': 'Most popular hashtags',
        'no_tags': 'No hashtags yet. Post with #tag!',
        'login_title': 'Log in',
        'register_title': 'Sign up',
        'login_placeholder': 'Username',
        'password_placeholder': 'Password',
        'confirm_placeholder': 'Repeat password',
        'no_account': 'No account?',
        'have_account': 'Already have an account?',
        'current_lang': 'Current language: English',
    }
}


def t(key):
    """Перевод по ключу для текущего языка."""
    lang = session.get('lang', 'ru')
    return TRANSLATIONS.get(lang, TRANSLATIONS['ru']).get(key, key)


# ============================================================
# УТИЛИТЫ
# ============================================================
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE, timeout=30)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
        g.db.execute('PRAGMA journal_mode=WAL')
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    return request.remote_addr or 'unknown'


def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT DEFAULT '',
                age INTEGER DEFAULT 0,
                city TEXT DEFAULT '',
                about TEXT DEFAULT '',
                avatar TEXT DEFAULT '',
                last_seen TIMESTAMP DEFAULT NULL,
                is_admin INTEGER DEFAULT 0,
                is_blocked INTEGER DEFAULT 0,
                muted_until TIMESTAMP DEFAULT NULL
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                image TEXT DEFAULT '',
                repost_of INTEGER DEFAULT NULL,
                views INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS post_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, user_id)
            )
        ''')
        db.commit()

        # ---- МИГРАЦИИ ----
        cols = [r[1] for r in db.execute("PRAGMA table_info(users)").fetchall()]
        if 'is_admin' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        if 'is_blocked' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0")
        if 'last_seen' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN last_seen TIMESTAMP DEFAULT NULL")
        if 'muted_until' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN muted_until TIMESTAMP DEFAULT NULL")
        db.commit()

        post_cols = [r[1] for r in db.execute("PRAGMA table_info(posts)").fetchall()]
        if 'repost_of' not in post_cols:
            db.execute("ALTER TABLE posts ADD COLUMN repost_of INTEGER DEFAULT NULL")
        if 'views' not in post_cols:
            db.execute("ALTER TABLE posts ADD COLUMN views INTEGER DEFAULT 0")
        db.commit()

        # ---- ОСТАЛЬНЫЕ ТАБЛИЦЫ ----
        init_messages_table()
        init_social_tables()
        init_follows_table()
        init_security_tables()

        db.execute("UPDATE posts SET image = '' WHERE image IS NULL")
        db.commit()


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему.', 'error')
            return redirect(url_for('login'))
        user = current_user()
        if user and user['is_blocked']:
            session.clear()
            flash('Ваш аккаунт заблокирован.', 'error')
            return redirect(url_for('login'))
        last = session.get('last_activity')
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if datetime.utcnow() - last_dt > timedelta(days=7):
                    session.clear()
                    flash('Сессия истекла, войдите снова', 'error')
                    return redirect(url_for('login'))
            except (ValueError, TypeError):
                pass
        session['last_activity'] = datetime.utcnow().isoformat()
        touch_last_seen(session['user_id'])
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Пожалуйста, войдите в систему.', 'error')
            return redirect(url_for('login'))
        user = current_user()
        if not user or not user['is_admin']:
            log_security_event('admin_access_denied',
                               username=session.get('username'),
                               ip=get_client_ip(),
                               details=request.path)
            abort(403)
        if user['is_blocked']:
            session.clear()
            flash('Ваш аккаунт заблокирован.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def is_muted(user):
    if not user or not user['muted_until']:
        return False
    try:
        muted_dt = datetime.strptime(str(user['muted_until'])[:19], '%Y-%m-%d %H:%M:%S')
        return datetime.utcnow() < muted_dt
    except (ValueError, TypeError):
        return False


def is_online(user_row):
    if not user_row or not user_row['last_seen']:
        return False
    try:
        last = datetime.strptime(str(user_row['last_seen'])[:19], '%Y-%m-%d %H:%M:%S')
        return (datetime.utcnow() - last).total_seconds() < 300
    except (ValueError, TypeError):
        return False


def current_user():
    if 'user_id' not in session:
        return None
    db = get_db()
    return db.execute(
        'SELECT * FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()


@app.context_processor
def inject_globals():
    user = current_user()
    return {
        'current_user': user,
        'is_admin': bool(user and user['is_admin']),
        'is_muted_now': is_muted(user) if user else False,
        'is_online': is_online,
        't': t,
        'lang': session.get('lang', 'ru'),
    }


# ============================================================
# CSRF
# ============================================================
def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = generate_csrf_token()
    return session['_csrf']


app.jinja_env.globals['csrf_token'] = csrf_token


@app.before_request
def csrf_protect():
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        token = session.get('_csrf')
        sent = request.headers.get('X-CSRF-Token')
        if not sent:
            sent = request.form.get('_csrf')
        if not sent and request.is_json:
            data = request.get_json(silent=True) or {}
            sent = data.get('_csrf')
        if not token or not sent or not _const_time_equal(token, sent):
            log_security_event('csrf_fail', ip=get_client_ip(),
                               details=f'{request.method} {request.path}')
            abort(403)


def _const_time_equal(a, b):
    import hmac
    return hmac.compare_digest(str(a), str(b))


# ============================================================
# SECURITY HEADERS
# ============================================================
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "font-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response


# ============================================================
# ERROR HANDLERS
# ============================================================
@app.errorhandler(403)
def err_403(e):
    return render_template('403.html'), 403


@app.errorhandler(404)
def err_404(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def err_500(e):
    log_security_event('500_error', ip=get_client_ip(), details=str(e))
    return render_template('500.html'), 500


@app.errorhandler(413)
def err_413(e):
    flash('Файл слишком большой (макс. 5 МБ)', 'error')
    return redirect(request.referrer or url_for('feed'))


# ============================================================
# JINJA ФИЛЬТРЫ
# ============================================================
def humanize_time(ts):
    if not ts:
        return ''
    try:
        dt = datetime.strptime(str(ts)[:19], '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        return str(ts)
    delta = datetime.utcnow() - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return 'только что'
    if secs < 3600:
        return f'{secs // 60} мин назад'
    if secs < 86400:
        return f'{secs // 3600} ч назад'
    if secs < 604800:
        return f'{secs // 86400} дн назад'
    return dt.strftime('%d.%m.%Y')


app.jinja_env.filters['humanize'] = humanize_time


def highlight_mentions_and_tags(text):
    from markupsafe import escape, Markup
    safe = str(escape(text))
    safe = re.sub(r'@(\w+)', r'<a href="/user/\1" class="mention">@\1</a>', safe)
    safe = re.sub(r'#(\w+)', r'<a href="/tag/\1" class="hashtag">#\1</a>', safe)
    return Markup(safe)


app.jinja_env.filters['highlight'] = highlight_mentions_and_tags


# ============================================================
# МАРШРУТЫ
# ============================================================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('feed'))
    return redirect(url_for('login'))


@app.route('/set-lang/<lang>')
def set_lang(lang):
    if lang not in ('ru', 'en'):
        lang = 'ru'
    session['lang'] = lang
    ref = request.referrer
    if ref:
        return redirect(ref)
    return redirect(url_for('profile'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('feed'))

    if request.method == 'POST':
        ip = get_client_ip()

        if not register_limiter.is_allowed(ip):
            log_security_event('register_rate_limit', ip=ip)
            flash('Слишком много попыток регистрации. Подождите.', 'error')
            return redirect(url_for('register'))

        register_limiter.hit(ip)

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')

        if not re.match(r'^[a-zA-Z0-9_А-Яа-яЁё]{3,20}$', username):
            flash('Логин: 3–20 символов, буквы/цифры/_', 'error')
            return redirect(url_for('register'))

        if not password:
            flash('Введите пароль', 'error')
            return redirect(url_for('register'))

        if password != confirm:
            flash('Пароли не совпадают', 'error')
            return redirect(url_for('register'))

        ok, msg = check_password_strength(password)
        if not ok:
            flash(msg, 'error')
            return redirect(url_for('register'))

        db = get_db()
        if db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone():
            flash('Такое имя пользователя уже занято', 'error')
            return redirect(url_for('register'))

        hashed = generate_password_hash(password)
        db.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                   (username, hashed))
        db.commit()

        log_security_event('register', username=username, ip=ip)
        flash('Регистрация успешна! Войдите.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('feed'))

    if request.method == 'POST':
        ip = get_client_ip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not login_limiter.is_allowed(ip):
            seconds = login_limiter.time_left(ip)
            log_security_event('login_rate_limit', username=username, ip=ip)
            flash(f'Слишком много попыток. Подождите {seconds} секунд.', 'error')
            return redirect(url_for('login'))

        if count_failed_recent(username, ip, 15) >= 10:
            log_security_event('login_db_rate_limit', username=username, ip=ip)
            flash('Слишком много неудачных попыток. Подождите 15 минут.', 'error')
            return redirect(url_for('login'))

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user and user['is_blocked']:
            log_security_event('login_blocked', username=username, ip=ip)
            flash('Аккаунт заблокирован.', 'error')
            return redirect(url_for('login'))

        if user and check_password_hash(user['password_hash'], password):
            login_limiter.reset(ip)
            log_login(username, ip, True)

            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['last_activity'] = datetime.utcnow().isoformat()
            session['_csrf'] = generate_csrf_token()
            session.permanent = True

            log_security_event('login_success', username=username, ip=ip)
            return redirect(url_for('feed'))

        login_limiter.hit(ip)
        log_login(username, ip, False)
        log_security_event('login_fail', username=username, ip=ip)

        flash('Неверное имя пользователя или пароль', 'error')

    return render_template('login.html')


@app.route('/feed', methods=['GET', 'POST'])
@login_required
def feed():
    user = current_user()
    db = get_db()
    tab = request.args.get('tab', 'all')

    if request.method == 'POST':
        if not user['is_admin'] and is_muted(user):
            flash('Вы в муте. Не можете публиковать.', 'error')
            return redirect(url_for('feed', tab=tab))

        ip = get_client_ip()
        if not post_limiter.is_allowed(ip):
            flash('Слишком часто публикуете. Подождите минуту.', 'error')
            return redirect(url_for('feed', tab=tab))
        post_limiter.hit(ip)

        content = request.form.get('content', '').strip()
        repost_of = request.form.get('repost_of', '').strip()

        if not content and not repost_of:
            flash('Пост не может быть пустым', 'error')
        elif len(content) > 280:
            flash('Пост слишком длинный (макс. 280)', 'error')
        else:
            repost_id = None
            if repost_of and repost_of.isdigit():
                original = db.execute('SELECT id FROM posts WHERE id = ?', (int(repost_of),)).fetchone()
                if original:
                    repost_id = original['id']

            image_name = ''
            file = request.files.get('image')
            if file and file.filename and not repost_id:
                ok, msg, ext = validate_upload(file)
                if not ok:
                    flash(msg, 'error')
                    return redirect(url_for('feed', tab=tab))
                image_name = f"{uuid4().hex}.{ext}"
                os.makedirs(app.config['POST_MEDIA_FOLDER'], exist_ok=True)
                file.save(os.path.join(app.config['POST_MEDIA_FOLDER'], image_name))

            db.execute('INSERT INTO posts (user_id, content, image, repost_of) VALUES (?, ?, ?, ?)',
                       (user['id'], content, image_name, repost_id))
            db.commit()
            flash('Пост опубликован!', 'success')
        return redirect(url_for('feed', tab=tab))

    if tab == 'following':
        following_ids = get_following_ids(user['id'])
        if not following_ids:
            posts = []
        else:
            ph = ','.join('?' * len(following_ids))
            posts = db.execute(f'''
                SELECT posts.id, posts.content, posts.created_at, posts.image,
                       posts.repost_of, posts.views,
                       users.username, users.avatar,
                       (SELECT COUNT(*) FROM posts p2 WHERE p2.repost_of = posts.id) AS repost_count
                FROM posts JOIN users ON users.id = posts.user_id
                WHERE posts.user_id IN ({ph})
                ORDER BY posts.created_at DESC
            ''', following_ids).fetchall()
    else:
        posts = db.execute('''
            SELECT posts.id, posts.content, posts.created_at, posts.image,
                   posts.repost_of, posts.views,
                   users.username, users.avatar,
                   (SELECT COUNT(*) FROM posts p2 WHERE p2.repost_of = posts.id) AS repost_count
            FROM posts JOIN users ON users.id = posts.user_id
            ORDER BY posts.created_at DESC
        ''').fetchall()

    post_ids = [p['id'] for p in posts]
    reactions = get_reactions_for_posts(post_ids, user['id'])
    comment_counts = count_comments_for_posts(post_ids)
    saved = get_saved_post_ids(user['id'])
    return render_template('feed.html', user=user, posts=posts,
                           reactions=reactions, comment_counts=comment_counts,
                           saved=saved, all_emojis=ALLOWED_EMOJIS, tab=tab)


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    user = current_user()
    db = get_db()
    post = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    if not post:
        flash('Пост не найден', 'error')
    elif post['user_id'] != user['id'] and not user['is_admin']:
        log_security_event('delete_foreign_post', username=user['username'],
                           ip=get_client_ip(), details=f'post_id={post_id}')
        flash('Это не ваш пост', 'error')
    else:
        db.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        db.execute('DELETE FROM reactions WHERE post_id = ?', (post_id,))
        db.execute('DELETE FROM comments WHERE post_id = ?', (post_id,))
        db.execute('DELETE FROM post_views WHERE post_id = ?', (post_id,))
        db.commit()
        flash('Пост удалён', 'success')

    return redirect(url_for('feed'))


@app.route('/post/<int:post_id>/react', methods=['POST'])
@login_required
def react_post(post_id):
    user = current_user()
    data = request.get_json(silent=True) or {}
    emoji = data.get('emoji', '')
    db = get_db()
    post = db.execute('SELECT user_id FROM posts WHERE id = ?', (post_id,)).fetchone()
    if not post:
        return jsonify({'error': 'not found'}), 404
    if not toggle_reaction(post_id, user['id'], emoji):
        return jsonify({'error': 'invalid'}), 400
    add_notification(post['user_id'], user['id'], 'reaction', post_id)
    r = get_reactions_for_post(post_id, user['id'])
    return jsonify({'counts': r['counts'], 'mine': r['mine']})


@app.route('/post/<int:post_id>/repost', methods=['POST'])
@login_required
def repost_post(post_id):
    user = current_user()
    if not user['is_admin'] and is_muted(user):
        return jsonify({'error': 'muted'}), 403

    db = get_db()
    original = db.execute('SELECT * FROM posts WHERE id = ?', (post_id,)).fetchone()
    if not original:
        return jsonify({'error': 'not found'}), 404
    if original['user_id'] == user['id']:
        return jsonify({'error': 'own_post'}), 400

    existing = db.execute(
        'SELECT id FROM posts WHERE user_id = ? AND repost_of = ?',
        (user['id'], post_id)
    ).fetchone()
    if existing:
        db.execute('DELETE FROM posts WHERE id = ?', (existing['id'],))
        db.commit()
        return jsonify({'reposted': False})

    db.execute('INSERT INTO posts (user_id, content, repost_of) VALUES (?, ?, ?)',
               (user['id'], '', post_id))
    db.commit()
    add_notification(original['user_id'], user['id'], 'repost', post_id)
    return jsonify({'reposted': True})


@app.route('/post/<int:post_id>/view', methods=['POST'])
@login_required
def view_post(post_id):
    user = current_user()
    db = get_db()
    post = db.execute('SELECT id, views FROM posts WHERE id = ?', (post_id,)).fetchone()
    if not post:
        return jsonify({'error': 'not found'}), 404

    existing = db.execute(
        'SELECT id FROM post_views WHERE post_id = ? AND user_id = ?',
        (post_id, user['id'])
    ).fetchone()
    if not existing:
        db.execute('INSERT INTO post_views (post_id, user_id) VALUES (?, ?)',
                   (post_id, user['id']))
        db.execute('UPDATE posts SET views = views + 1 WHERE id = ?', (post_id,))
        db.commit()
        return jsonify({'views': (post['views'] or 0) + 1, 'counted': True})

    return jsonify({'views': post['views'] or 0, 'counted': False})


@app.route('/post/<int:post_id>/save', methods=['POST'])
@login_required
def save_post(post_id):
    user = current_user()
    db = get_db()
    if not db.execute('SELECT id FROM posts WHERE id = ?', (post_id,)).fetchone():
        return jsonify({'error': 'not found'}), 404
    state = toggle_save_post(user['id'], post_id)
    return jsonify({'saved': state})


@app.route('/saved')
@login_required
def saved_posts():
    user = current_user()
    db = get_db()
    saved_ids = get_saved_post_ids(user['id'])
    if not saved_ids:
        posts = []
    else:
        ph = ','.join('?' * len(saved_ids))
        posts = db.execute(f'''
            SELECT posts.id, posts.content, posts.created_at, posts.image,
                   posts.repost_of, posts.views,
                   users.username, users.avatar,
                   (SELECT COUNT(*) FROM posts p2 WHERE p2.repost_of = posts.id) AS repost_count
            FROM posts JOIN users ON users.id = posts.user_id
            WHERE posts.id IN ({ph})
            ORDER BY posts.created_at DESC
        ''', list(saved_ids)).fetchall()
    post_ids = [p['id'] for p in posts]
    reactions = get_reactions_for_posts(post_ids, user['id'])
    comment_counts = count_comments_for_posts(post_ids)
    return render_template('saved.html', user=user, posts=posts,
                           reactions=reactions, comment_counts=comment_counts,
                           saved=saved_ids, all_emojis=ALLOWED_EMOJIS)


@app.route('/post/<int:post_id>/comments', methods=['GET', 'POST'])
@login_required
def post_comments(post_id):
    user = current_user()
    db = get_db()
    post = db.execute('SELECT user_id FROM posts WHERE id = ?', (post_id,)).fetchone()
    if not post:
        return jsonify({'error': 'not found'}), 404

    if request.method == 'POST':
        if not user['is_admin'] and is_muted(user):
            return jsonify({'error': 'muted'}), 403

        ip = get_client_ip()
        if not comment_limiter.is_allowed(ip):
            return jsonify({'error': 'rate_limit'}), 429
        comment_limiter.hit(ip)

        data = request.get_json(silent=True) or {}
        content = (data.get('content') or '').strip()
        if not content or len(content) > 500:
            return jsonify({'error': 'invalid'}), 400
        add_comment(post_id, user['id'], content)
        add_notification(post['user_id'], user['id'], 'comment', post_id)

    comments = get_comments_for_post(post_id)
    return jsonify({
        'comments': [
            {
                'id': c['id'],
                'content': c['content'],
                'created_at': humanize_time(c['created_at']),
                'username': c['username'],
                'avatar': c['avatar'] or '',
                'is_mine': c['user_id'] == user['id'],
            } for c in comments
        ]
    })


@app.route('/tag/<tag>')
@login_required
def tag_feed(tag):
    user = current_user()
    db = get_db()
    if not re.match(r'^\w{1,50}$', tag):
        flash('Некорректный тег', 'error')
        return redirect(url_for('feed'))
    posts = db.execute('''
        SELECT posts.id, posts.content, posts.created_at, posts.image,
               posts.repost_of, posts.views,
               users.username, users.avatar,
               (SELECT COUNT(*) FROM posts p2 WHERE p2.repost_of = posts.id) AS repost_count
        FROM posts JOIN users ON users.id = posts.user_id
        WHERE posts.content LIKE ?
        ORDER BY posts.created_at DESC
    ''', (f'%#{tag}%',)).fetchall()
    post_ids = [p['id'] for p in posts]
    reactions = get_reactions_for_posts(post_ids, user['id'])
    comment_counts = count_comments_for_posts(post_ids)
    saved = get_saved_post_ids(user['id'])
    return render_template('feed.html', user=user, posts=posts,
                           reactions=reactions, comment_counts=comment_counts,
                           saved=saved, all_emojis=ALLOWED_EMOJIS,
                           tab='all', tag=tag)


@app.route('/trends')
@login_required
def trends():
    user = current_user()
    db = get_db()

    rows = db.execute("SELECT content FROM posts WHERE content LIKE '%#%'").fetchall()
    hashtag_count = {}
    for row in rows:
        for tag in re.findall(r'#(\w+)', row['content']):
            tag_lower = tag.lower()
            hashtag_count[tag_lower] = hashtag_count.get(tag_lower, 0) + 1

    top_tags = sorted(hashtag_count.items(), key=lambda x: -x[1])[:30]

    return render_template('trends.html', user=user, tags=top_tags)


@app.route('/search')
@login_required
def search():
    user = current_user()
    q = request.args.get('q', '').strip()[:50]
    results = []
    if q:
        db = get_db()
        results = db.execute('''
            SELECT id, username, full_name, avatar
            FROM users
            WHERE username LIKE ? OR full_name LIKE ?
            LIMIT 30
        ''', (f'%{q}%', f'%{q}%')).fetchall()
    return render_template('search.html', user=user, q=q, results=results)


# ============================================================
# ПРОФИЛЬ (свой)
# ============================================================
@app.route('/profile')
@login_required
def profile():
    user = current_user()
    db = get_db()

    posts_count = db.execute(
        'SELECT COUNT(*) FROM posts WHERE user_id = ?', (user['id'],)
    ).fetchone()[0]

    admin_data = None
    if user['is_admin']:
        admin_data = {
            'stats': {
                'users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
                'posts': db.execute('SELECT COUNT(*) FROM posts').fetchone()[0],
                'messages': db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],
                'blocked': db.execute('SELECT COUNT(*) FROM users WHERE is_blocked = 1').fetchone()[0],
                'muted': db.execute(
                    "SELECT COUNT(*) FROM users WHERE muted_until IS NOT NULL AND muted_until > datetime('now')"
                ).fetchone()[0],
            },
            'users': db.execute('''
                SELECT id, username, full_name, avatar, is_admin, is_blocked, muted_until,
                       (SELECT COUNT(*) FROM posts WHERE user_id = users.id) AS posts_count
                FROM users
                ORDER BY id DESC
                LIMIT 100
            ''').fetchall(),
            'events': db.execute('''
                SELECT * FROM security_log
                ORDER BY id DESC
                LIMIT 20
            ''').fetchall(),
        }

    return render_template('profile.html',
                           user=user,
                           posts_count=posts_count,
                           followers_count=get_followers_count(user['id']),
                           following_count=get_following_count(user['id']),
                           admin_data=admin_data)


@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def profile_edit():
    user = current_user()
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()[:100]
        city = request.form.get('city', '').strip()[:100]
        about = request.form.get('about', '').strip()[:500]
        age_str = request.form.get('age', '').strip()
        age = 0
        if age_str:
            if not age_str.isdigit():
                flash('Возраст — число', 'error')
                return redirect(url_for('profile_edit'))
            age = int(age_str)
            if age < 0 or age > 150:
                flash('Возраст от 0 до 150', 'error')
                return redirect(url_for('profile_edit'))

        avatar_filename = user['avatar']
        file = request.files.get('avatar')
        if file and file.filename:
            ok, msg, ext = validate_upload(file)
            if not ok:
                flash(msg, 'error')
                return redirect(url_for('profile_edit'))
            new_name = f"{uuid4().hex}.{ext}"
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], new_name))
            if user['avatar']:
                old = os.path.join(app.config['UPLOAD_FOLDER'], user['avatar'])
                if os.path.exists(old):
                    try:
                        os.remove(old)
                    except OSError:
                        pass
            avatar_filename = new_name

        db = get_db()
        db.execute('''UPDATE users SET full_name=?, age=?, city=?, about=?, avatar=?
                      WHERE id=?''',
                   (full_name, age, city, about, avatar_filename, user['id']))
        db.commit()
        flash('Профиль обновлён!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile_edit.html', user=user)


# ============================================================
# ЧУЖОЙ ПРОФИЛЬ
# ============================================================
@app.route('/user/<username>')
@login_required
def user_profile(username):
    if not re.match(r'^[a-zA-Z0-9_А-Яа-яЁё]{1,50}$', username):
        abort(404)
    viewer = current_user()
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('feed'))

    posts = db.execute('''
        SELECT posts.id, posts.content, posts.created_at, posts.image,
               posts.repost_of, posts.views,
               users.username, users.avatar,
               (SELECT COUNT(*) FROM posts p2 WHERE p2.repost_of = posts.id) AS repost_count
        FROM posts JOIN users ON users.id = posts.user_id
        WHERE users.id = ? ORDER BY posts.created_at DESC
    ''', (user['id'],)).fetchall()

    post_ids = [p['id'] for p in posts]
    reactions = get_reactions_for_posts(post_ids, viewer['id'])
    comment_counts = count_comments_for_posts(post_ids)
    saved = get_saved_post_ids(viewer['id'])
    return render_template('user_profile.html', user=user, posts=posts,
                           reactions=reactions, comment_counts=comment_counts,
                           saved=saved, all_emojis=ALLOWED_EMOJIS,
                           posts_count=len(posts),
                           followers_count=get_followers_count(user['id']),
                           following_count=get_following_count(user['id']),
                           is_following=is_following(viewer['id'], user['id']),
                           is_self=(user['id'] == viewer['id']))


@app.route('/user/<username>/follow', methods=['POST'])
@login_required
def follow_user(username):
    if not re.match(r'^[a-zA-Z0-9_А-Яа-яЁё]{1,50}$', username):
        return jsonify({'error': 'invalid'}), 400
    viewer = current_user()
    db = get_db()
    target = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if not target or target['id'] == viewer['id']:
        return jsonify({'error': 'invalid'}), 400
    state = toggle_follow(viewer['id'], target['id'])
    if state == 'followed':
        add_notification(target['id'], viewer['id'], 'follow')
    return jsonify({'state': state, 'followers': get_followers_count(target['id'])})


# ============================================================
# 👑 АДМИН-ДЕЙСТВИЯ
# ============================================================
@app.route('/admin/user/<int:user_id>/block', methods=['POST'])
@admin_required
def admin_block_user(user_id):
    db = get_db()
    target = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not target:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('profile'))
    if target['id'] == session['user_id']:
        flash('Нельзя блокировать самого себя', 'error')
        return redirect(url_for('profile'))

    new_state = 0 if target['is_blocked'] else 1
    db.execute('UPDATE users SET is_blocked = ? WHERE id = ?', (new_state, user_id))
    db.commit()
    log_security_event('admin_block' if new_state else 'admin_unblock',
                       username=session.get('username'), ip=get_client_ip(),
                       details=f'target={target["username"]}')
    flash(f'@{target["username"]} {"забанен" if new_state else "разбанен"}', 'success')
    return redirect(url_for('profile'))


@app.route('/admin/user/<int:user_id>/mute', methods=['POST'])
@admin_required
def admin_mute_user(user_id):
    db = get_db()
    target = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not target:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('profile'))
    if target['id'] == session['user_id']:
        flash('Нельзя замутить себя', 'error')
        return redirect(url_for('profile'))

    minutes = request.form.get('minutes', '60')
    try:
        minutes = int(minutes)
    except ValueError:
        minutes = 60
    if minutes < 1:
        minutes = 1
    if minutes > 60 * 24 * 30:
        minutes = 60 * 24 * 30

    if target['muted_until']:
        try:
            muted_dt = datetime.strptime(str(target['muted_until'])[:19], '%Y-%m-%d %H:%M:%S')
            if datetime.utcnow() < muted_dt:
                db.execute('UPDATE users SET muted_until = NULL WHERE id = ?', (user_id,))
                db.commit()
                log_security_event('admin_unmute', username=session.get('username'),
                                   ip=get_client_ip(), details=f'target={target["username"]}')
                flash(f'@{target["username"]} размучен', 'success')
                return redirect(url_for('profile'))
        except (ValueError, TypeError):
            pass

    until = datetime.utcnow() + timedelta(minutes=minutes)
    db.execute('UPDATE users SET muted_until = ? WHERE id = ?',
               (until.strftime('%Y-%m-%d %H:%M:%S'), user_id))
    db.commit()
    log_security_event('admin_mute', username=session.get('username'),
                       ip=get_client_ip(),
                       details=f'target={target["username"]}, minutes={minutes}')
    flash(f'@{target["username"]} в муте на {minutes} мин.', 'success')
    return redirect(url_for('profile'))


@app.route('/admin/user/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def admin_toggle_admin(user_id):
    db = get_db()
    target = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not target:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('profile'))
    if target['id'] == session['user_id']:
        flash('Нельзя снять админку с себя', 'error')
        return redirect(url_for('profile'))

    new_state = 0 if target['is_admin'] else 1
    db.execute('UPDATE users SET is_admin = ? WHERE id = ?', (new_state, user_id))
    db.commit()
    log_security_event('admin_grant' if new_state else 'admin_revoke',
                       username=session.get('username'), ip=get_client_ip(),
                       details=f'target={target["username"]}')
    flash(f'@{target["username"]} {"теперь админ" if new_state else "больше не админ"}', 'success')
    return redirect(url_for('profile'))


@app.route('/admin/security-log')
@admin_required
def admin_security_log():
    db = get_db()
    events = db.execute('SELECT * FROM security_log ORDER BY id DESC LIMIT 500').fetchall()
    return render_template('admin_log.html', user=current_user(), events=events)


# ============================================================
# УВЕДОМЛЕНИЯ
# ============================================================
@app.route('/notifications')
@login_required
def notifications():
    user = current_user()
    mark_notifications_read(user['id'])
    items = get_notifications(user['id'])
    return render_template('notifications.html', user=user, items=items)


# ============================================================
# ЧАТЫ
# ============================================================
@app.route('/chats')
@login_required
def chats():
    user = current_user()
    dialogs = get_dialogs(user['id'])
    return render_template('chats.html', user=user, dialogs=dialogs)


@app.route('/chat/<username>', methods=['GET', 'POST'])
@login_required
def chat(username):
    if not re.match(r'^[a-zA-Z0-9_А-Яа-яЁё]{1,50}$', username):
        abort(404)
    user = current_user()
    db = get_db()
    other = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    if not other:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('chats'))
    if other['id'] == user['id']:
        flash('Нельзя писать самому себе', 'error')
        return redirect(url_for('chats'))
    if request.method == 'POST':
        if not user['is_admin'] and is_muted(user):
            flash('Вы в муте. Не можете отправлять сообщения.', 'error')
            return redirect(url_for('chat', username=username))

        content = request.form.get('content', '').strip()
        if content and len(content) <= 2000:
            send_message(user['id'], other['id'], content)
        return redirect(url_for('chat', username=username))
    mark_as_read(user['id'], other['id'])
    messages = get_conversation(user['id'], other['id'])
    return render_template('chat.html', user=user, other=other, messages=messages)


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('login'))


# ============================================================
# ЗАПУСК
# ============================================================
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['POST_MEDIA_FOLDER'], exist_ok=True)
with app.app_context():
    init_db()

if __name__ == '__main__':
    debug_mode = os.environ.get('AURA_DEBUG', '0') == '1'
    app.run(debug=debug_mode, host='127.0.0.1', port=5000)