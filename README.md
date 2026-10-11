<div align="center">

# 🌐 Aura

### Мини-соцсеть на Flask с акцентом на безопасность

🔗 **[→ Живая демонстрация ←](https://aura-flask-l5sb.onrender.com)**

---

[![Live Demo](https://img.shields.io/badge/Live_Demo-Online-00ba7c?style=for-the-badge&logo=render&logoColor=white)](https://aura-flask-l5sb.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Tests](https://img.shields.io/badge/Tests-6%2F6_passed-00ba7c?style=for-the-badge)](https://github.com/noizon/Aura-flask)

</div>

---

## ✨ Что умеет

| | |
|---|---|
| 👤 **Аккаунты** | Регистрация, вход, профили с аватарами |
| 📝 **Посты** | Фото, реакции, комментарии, репосты, закладки |
| 💬 **Чаты** | Личные сообщения и диалоги |
| 👥 **Соцсеть** | Подписки, лента, уведомления, поиск, онлайн-статус |
| 🔥 **Тренды** | Топ хэштегов |
| 👑 **Админка** | Бан, мут, назначение админов, security log |
| 🌐 **Языки** | Русский / English |

## 🛡 Безопасность

- **CSRF** — `hmac.compare_digest` на всех POST
- **Rate limiting** — 5 логинов/15 мин, 3 регистрации/час
- **Хэширование** — Werkzeug (PBKDF2 + salt)
- **SQL-инъекции** — только параметризованные запросы
- **XSS** — Jinja autoescape + кастомный фильтр
- **Валидация файлов** — проверка magic bytes
- **Security headers** — CSP, X-Frame-Options, nosniff
- **Security log** — все события в БД

## 🛠 Стек

`Flask` · `SQLite` · `Werkzeug` · `Jinja2` · `HTML` · `CSS` · `JavaScript`

> Без внешних CSS/JS-библиотек — всё написано вручную.

## 🚀 Запуск

```bash
git clone https://github.com/noizon/Aura-flask.git
cd Aura-flask
pip install -r requirements.txt
python app.py
Открыть → http://127.0.0.1:5000

🧪 Тесты
bash
python test_app.py
6 / 6 passed — SQL-инъекции, CSRF, rate limit, XSS, чужой пост, path traversal.

📁 Структура
text
Aura-flask/
├── app.py              # Роуты, конфиг
├── messages_db.py      # Чаты
├── social_db.py        # Реакции, комментарии
├── follow_db.py        # Подписки, уведомления
├── security.py         # CSRF, rate limiter, валидация
├── security_db.py      # Логи безопасности
├── test_app.py         # 6 автотестов
├── templates/          # HTML-шаблоны
└── static/             # CSS, иконки
<div align="center">
NoiZoN · 2 курс · IT Hub

GitHub · Telegram

</div> ```
