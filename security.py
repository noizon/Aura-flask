"""
Утилиты безопасности для Aura.
Всё, что связано с защитой — здесь.
"""
import os
import re
import secrets
import hashlib
from datetime import datetime, timedelta

# ============================================================
# CSRF-токены
# ============================================================
def generate_csrf_token():
    """Генерирует случайный CSRF-токен."""
    return secrets.token_urlsafe(32)


# ============================================================
# Проверка сложности пароля
# ============================================================
COMMON_PASSWORDS = {
    '123456', '12345678', 'qwerty', 'password', '12345',
    '123456789', 'letmein', '1234567', 'admin', 'welcome',
    'monkey', '1234567890', 'abc123', '111111', 'qwerty123',
    'qwertyuiop', 'password1', '123123', 'admin123', 'root',
    'пароль', 'йцукен', '1111', '2222', '0000'
}


def check_password_strength(password):
    """
    Возвращает (ok: bool, message: str).
    Требования:
    - минимум 8 символов
    - хотя бы одна буква (a-z / а-я)
    - хотя бы одна цифра
    - не в списке популярных
    """
    if len(password) < 8:
        return False, 'Пароль должен быть не короче 8 символов'

    if password.lower() in COMMON_PASSWORDS:
        return False, 'Такой пароль слишком популярный — его подберут за секунду'

    if not re.search(r'[A-Za-zА-Яа-я]', password):
        return False, 'Пароль должен содержать хотя бы одну букву'

    if not re.search(r'\d', password):
        return False, 'Пароль должен содержать хотя бы одну цифру'

    if len(set(password)) < 4:
        return False, 'Слишком мало уникальных символов в пароле'

    return True, 'OK'


# ============================================================
# Безопасная работа с загружаемыми файлами
# ============================================================
# Магические байты для распознавания типа файла
MAGIC_BYTES = {
    b'\xff\xd8\xff': 'jpg',      # JPEG
    b'\x89PNG\r\n\x1a\n': 'png', # PNG
    b'GIF87a': 'gif',            # GIF87
    b'GIF89a': 'gif',            # GIF89
    b'RIFF': 'webp',             # WebP (нужна доп. проверка)
}

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_MIMES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}


def is_safe_filename(filename):
    """Проверяет, что имя файла не содержит опасных символов."""
    if not filename:
        return False
    # Никаких .., /, \, нулевых байтов
    if '..' in filename or '/' in filename or '\\' in filename:
        return False
    if '\x00' in filename:
        return False
    return True


def get_extension(filename):
    """Возвращает расширение файла в нижнем регистре без точки."""
    if '.' not in filename:
        return ''
    return filename.rsplit('.', 1)[1].lower()


def check_file_magic(file_stream):
    """
    Читает первые байты файла и определяет реальный тип.
    Возвращает 'jpg' / 'png' / 'gif' / 'webp' или None.
    Не забудь вернуть stream в начало через file_stream.seek(0).
    """
    head = file_stream.read(32)
    file_stream.seek(0)

    for magic, ftype in MAGIC_BYTES.items():
        if head.startswith(magic):
            # Для WebP проверяем точнее
            if magic == b'RIFF':
                if len(head) >= 12 and head[8:12] == b'WEBP':
                    return 'webp'
                continue
            return ftype
    return None


def validate_upload(file):
    """
    Полная проверка загружаемого изображения.
    Возвращает (ok: bool, message: str, ext: str).
    """
    if not file or not file.filename:
        return False, 'Файл не выбран', ''

    if not is_safe_filename(file.filename):
        return False, 'Недопустимое имя файла', ''

    ext = get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        return False, 'Разрешены только PNG, JPG, JPEG, GIF, WEBP', ''

    real_type = check_file_magic(file.stream)
    if not real_type:
        return False, 'Файл не является изображением', ''

    # Расширение должно совпадать с реальным типом (или быть jpeg для jpg)
    if real_type == 'jpg' and ext not in ('jpg', 'jpeg'):
        return False, 'Расширение не соответствует содержимому', ''
    if real_type != 'jpg' and real_type != ext:
        return False, 'Расширение не соответствует содержимому', ''

    return True, 'OK', ext


# ============================================================
# Rate limiting — простой in-memory счётчик
# ============================================================
class RateLimiter:
    """
    Простой rate limiter в памяти.
    Хранит словарь {key: [(timestamp, ...), ...]} и чистит старые.
    """
    def __init__(self, max_attempts, window_seconds):
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)
        self.data = {}

    def _clean(self, key):
        now = datetime.utcnow()
        if key in self.data:
            self.data[key] = [
                ts for ts in self.data[key]
                if now - ts < self.window
            ]

    def is_allowed(self, key):
        """Проверяет, можно ли выполнить действие. Не увеличивает счётчик."""
        self._clean(key)
        return len(self.data.get(key, [])) < self.max_attempts

    def hit(self, key):
        """Регистрирует попытку."""
        self._clean(key)
        self.data.setdefault(key, []).append(datetime.utcnow())

    def reset(self, key):
        """Сбрасывает счётчик (например, при успешном входе)."""
        self.data.pop(key, None)

    def time_left(self, key):
        """Сколько секунд до снятия блокировки."""
        self._clean(key)
        if key not in self.data or not self.data[key]:
            return 0
        oldest = min(self.data[key])
        delta = self.window - (datetime.utcnow() - oldest)
        return max(0, int(delta.total_seconds()))


# ============================================================
# Хэширование для логов (не логируем пароли/токены в чистом виде)
# ============================================================
def short_hash(value):
    """Быстрый хэш для логирования (не для паролей!)."""
    if not value:
        return ''
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]


# ============================================================
# Проверка "безопасного" реферера (для редиректов)
# ============================================================
def is_safe_redirect_url(url):
    """Разрешает редирект только на свой сайт (относительные пути)."""
    if not url:
        return False
    # Только относительные пути, начинающиеся с /
    if url.startswith('/') and not url.startswith('//'):
        return True
    return False