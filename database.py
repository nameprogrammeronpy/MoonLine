import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash

DATABASE = 'moonline.db'

def get_db():
    """Получить соединение с БД"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных"""
    conn = get_db()
    cursor = conn.cursor()

    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            avatar_color TEXT DEFAULT '#64C4ED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица записей дневника настроения
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mood_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            mood INTEGER NOT NULL CHECK(mood >= 1 AND mood <= 5),
            note TEXT,
            ai_insight TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Таблица истории чата с AI
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Таблица настроек пользователя
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            theme TEXT DEFAULT 'dark',
            notifications INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

# ============ USER FUNCTIONS ============

def create_user(username, password, email=None):
    """Создать пользователя"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
            (username, generate_password_hash(password), email)
        )
        user_id = cursor.lastrowid

        # Создаём настройки по умолчанию
        cursor.execute(
            'INSERT INTO user_settings (user_id) VALUES (?)',
            (user_id,)
        )

        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_username(username):
    """Получить пользователя по имени"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id):
    """Получить пользователя по ID"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def update_user(user_id, **kwargs):
    """Обновить данные пользователя"""
    conn = get_db()
    cursor = conn.cursor()

    allowed_fields = ['username', 'email', 'avatar_color', 'password']
    updates = []
    values = []

    for field, value in kwargs.items():
        if field in allowed_fields and value:
            if field == 'password':
                value = generate_password_hash(value)
            updates.append(f'{field} = ?')
            values.append(value)

    if updates:
        values.append(user_id)
        cursor.execute(
            f'UPDATE users SET {", ".join(updates)} WHERE id = ?',
            values
        )
        conn.commit()

    conn.close()

# ============ MOOD FUNCTIONS ============

def add_mood_entry(user_id, mood, note=None, ai_insight=None):
    """Добавить запись о настроении"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO mood_entries (user_id, mood, note, ai_insight) VALUES (?, ?, ?, ?)',
        (user_id, mood, note, ai_insight)
    )
    entry_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return entry_id

def get_mood_entries(user_id, limit=30):
    """Получить записи настроения пользователя"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM mood_entries WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    )
    entries = cursor.fetchall()
    conn.close()
    return [dict(e) for e in entries]

def get_mood_stats(user_id):
    """Получить статистику настроений"""
    conn = get_db()
    cursor = conn.cursor()

    # Средний показатель
    cursor.execute(
        'SELECT AVG(mood) as avg_mood, COUNT(*) as total FROM mood_entries WHERE user_id = ?',
        (user_id,)
    )
    stats = dict(cursor.fetchone())

    # Распределение по настроениям
    cursor.execute(
        'SELECT mood, COUNT(*) as count FROM mood_entries WHERE user_id = ? GROUP BY mood',
        (user_id,)
    )
    distribution = {row['mood']: row['count'] for row in cursor.fetchall()}

    # Последние 7 дней
    cursor.execute('''
        SELECT DATE(created_at) as date, AVG(mood) as avg_mood 
        FROM mood_entries 
        WHERE user_id = ? AND created_at >= datetime('now', '-7 days')
        GROUP BY DATE(created_at)
        ORDER BY date
    ''', (user_id,))
    weekly = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        'average': round(stats['avg_mood'], 2) if stats['avg_mood'] else 0,
        'total': stats['total'],
        'distribution': distribution,
        'weekly': weekly
    }

# ============ CHAT FUNCTIONS ============

def add_chat_message(user_id, role, content):
    """Добавить сообщение в чат"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO chat_messages (user_id, role, content) VALUES (?, ?, ?)',
        (user_id, role, content)
    )
    conn.commit()
    conn.close()

def get_chat_history(user_id, limit=50):
    """Получить историю чата"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM chat_messages WHERE user_id = ? ORDER BY created_at ASC LIMIT ?',
        (user_id, limit)
    )
    messages = cursor.fetchall()
    conn.close()
    return [dict(m) for m in messages]

def clear_chat_history(user_id):
    """Очистить историю чата"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM chat_messages WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_recent_messages(user_id, limit=10):
    """Получить последние сообщения для контекста AI"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT role, content FROM chat_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    )
    messages = cursor.fetchall()
    conn.close()
    return [{'role': m['role'], 'content': m['content']} for m in reversed(messages)]

# ============ SETTINGS FUNCTIONS ============

def get_user_settings(user_id):
    """Получить настройки пользователя"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
    settings = cursor.fetchone()
    conn.close()
    return dict(settings) if settings else {'theme': 'dark', 'notifications': 1}

def update_user_settings(user_id, **kwargs):
    """Обновить настройки"""
    conn = get_db()
    cursor = conn.cursor()

    allowed = ['theme', 'notifications']
    updates = []
    values = []

    for field, value in kwargs.items():
        if field in allowed:
            updates.append(f'{field} = ?')
            values.append(value)

    if updates:
        values.append(user_id)
        cursor.execute(
            f'UPDATE user_settings SET {", ".join(updates)} WHERE user_id = ?',
            values
        )
        conn.commit()

    conn.close()

# Инициализация при импорте
if __name__ == '__main__':
    init_db()

