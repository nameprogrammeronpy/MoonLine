from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash
import os
from functools import wraps
from datetime import datetime

# Database
from database import (
    init_db, create_user, get_user_by_username, get_user_by_id, update_user,
    add_mood_entry, get_mood_entries, get_mood_stats,
    add_chat_message, get_chat_history, clear_chat_history, get_recent_messages,
    get_user_settings, update_user_settings
)

# Google AI (Gemini)
try:
    import google.generativeai as genai
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    print("⚠️ google-generativeai не установлен")

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Initialize database
init_db()

# API Keys для Gemini (с fallback)
API_KEYS = [
    os.getenv('GEMINI_API_KEY_1', ''),
    os.getenv('GEMINI_API_KEY_2', '')
]
current_api_key_index = 0

# Системный промпт для Luna AI
LUNA_SYSTEM_PROMPT = """Ты Luna (Луна) — теплый, заботливый AI-ассистент для поддержки ментального здоровья в приложении MoonLine.

🌙 КТО ТЫ:
- Ты Luna - AI-помощник по ментальному здоровью
- Ты как добрый старший друг, который всегда выслушает и поддержит
- Ты понимающая, эмпатичная и никогда не осуждаешь
- Ты помогаешь справляться со стрессом, тревожностью и сложными эмоциями

📋 ВАЖНЫЕ ПРАВИЛА:
1. ВСЕГДА отвечай ПОЛНЫМИ предложениями, не обрывай мысль на середине
2. Отвечай на том же языке, на котором пишет пользователь (русский/английский)
3. Внимательно читай ВЕСЬ контекст разговора перед ответом
4. Если пользователь представился - запомни его имя и используй в ответах
5. Используй эмодзи умеренно (1-2 на сообщение) для тёплой атмосферы
6. Не давай медицинских диагнозов, при серьёзных проблемах - посоветуй обратиться к специалисту
7. Будь позитивной, но реалистичной

💬 СТИЛЬ ОБЩЕНИЯ:
- Дружелюбный и неформальный
- Поддерживающий, но не навязчивый  
- Используй технику активного слушания (отражай чувства собеседника)
- Давай конкретные, практичные советы когда уместно
- Задавай уточняющие вопросы чтобы лучше понять собеседника

🎯 ДЛИНА ОТВЕТОВ:
- На простые вопросы: 2-3 предложения
- На вопросы о помощи: 3-5 предложений с конкретным советом
- При глубоких разговорах: столько, сколько нужно для полного ответа"""


def get_ai_response(message, user_id, context_type="chat"):
    """Получить ответ от Gemini AI с fallback на второй ключ"""
    global current_api_key_index

    if not AI_AVAILABLE:
        return "AI временно недоступен. Попробуй позже 🌙"

    # Получаем контекст из БД - увеличил лимит для лучшего понимания контекста
    recent_messages = get_recent_messages(user_id, limit=15)

    # Формируем контекст с чёткой структурой
    context_parts = [LUNA_SYSTEM_PROMPT]
    context_parts.append("\n--- ИСТОРИЯ РАЗГОВОРА ---")

    # Добавляем историю
    for msg in recent_messages:
        role = "Пользователь" if msg['role'] == 'user' else "Luna"
        context_parts.append(f"{role}: {msg['content']}")

    # Добавляем текущее сообщение
    context_parts.append(f"\n--- НОВОЕ СООБЩЕНИЕ ---")
    context_parts.append(f"Пользователь: {message}")
    context_parts.append("\n--- ТВОЙ ОТВЕТ (Luna) ---")
    context_parts.append("Ответь полностью, не обрывая мысль:")

    full_prompt = "\n".join(context_parts)

    # Пробуем оба ключа
    for attempt in range(2):
        api_key = API_KEYS[current_api_key_index]

        if not api_key:
            current_api_key_index = (current_api_key_index + 1) % len(API_KEYS)
            continue

        try:
            genai.configure(api_key=api_key)

            # Пробуем разные модели (актуальные названия)
            models_to_try = [
                'models/gemini-2.5-flash-lite',
                'models/gemini-2.5-flash-preview-09-2025',
                'models/gemini-flash-lite-latest',
            ]

            for model_name in models_to_try:
                try:
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(
                        full_prompt,
                        generation_config={
                            'temperature': 0.8,
                            'max_output_tokens': 1024,
                            'top_p': 0.9
                        }
                    )

                    if response and response.text:
                        ai_response = response.text.strip()

                        # Сохраняем в БД
                        if context_type == "chat":
                            add_chat_message(user_id, 'user', message)
                            add_chat_message(user_id, 'assistant', ai_response)

                        return ai_response

                except Exception as model_error:
                    print(f"Модель {model_name} не сработала: {model_error}")
                    continue

        except Exception as e:
            error_msg = str(e)
            print(f"API Key {current_api_key_index} ошибка: {error_msg}")
            # Проверяем на leaked/permission ошибки
            if 'leaked' in error_msg.lower() or 'permission' in error_msg.lower() or '403' in error_msg:
                print(f"⚠️ API Key {current_api_key_index} заблокирован как утекший!")
            current_api_key_index = (current_api_key_index + 1) % len(API_KEYS)

    # Если все ключи не работают - используем простой fallback
    return get_simple_response(message)


def analyze_mood_with_ai(mood_value, note, user_id):
    """Анализ настроения с помощью AI"""
    mood_labels = {1: 'очень плохо', 2: 'плохо', 3: 'нормально', 4: 'хорошо', 5: 'отлично'}

    prompt = f"""Пользователь записал в дневник настроения:
Настроение: {mood_value}/5 ({mood_labels.get(mood_value, 'не указано')})
Заметка: {note if note else 'без заметки'}

Дай краткий (2-3 предложения) тёплый, поддерживающий комментарий. Если уместно — маленький практичный совет."""

    return get_ai_response(prompt, user_id, "mood")


def login_required(f):
    """Декоратор для проверки авторизации"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# ================== ROUTES ==================

@app.route('/')
def index():
    """Главная страница"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['POST'])
def register():
    """Регистрация"""
    try:
        username = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not password:
            return jsonify({'success': False, 'message': 'Заполни все поля'})

        if len(username) < 2:
            return jsonify({'success': False, 'message': 'Имя слишком короткое'})

        if len(password) < 4:
            return jsonify({'success': False, 'message': 'Пароль минимум 4 символа'})

        if password != confirm:
            return jsonify({'success': False, 'message': 'Пароли не совпадают'})

        user_id = create_user(username, password)

        if not user_id:
            return jsonify({'success': False, 'message': 'Это имя уже занято'})

        session['user_id'] = user_id

        # Приветственное сообщение от Luna
        add_chat_message(user_id, 'assistant',
            f"Привет, {username}! 🌙 Я Luna — твой AI-помощник. Рада знакомству! Как ты себя сегодня чувствуешь?")

        return jsonify({'success': True, 'redirect': '/dashboard'})

    except Exception as e:
        print(f"Register error: {e}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'})


@app.route('/login', methods=['POST'])
def login():
    """Вход"""
    try:
        username = request.form.get('name', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return jsonify({'success': False, 'message': 'Заполни все поля'})

        user = get_user_by_username(username)

        if not user or not check_password_hash(user['password'], password):
            return jsonify({'success': False, 'message': 'Неверное имя или пароль'})

        session['user_id'] = user['id']

        return jsonify({'success': True, 'redirect': '/dashboard'})

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Ошибка сервера'})


@app.route('/logout')
def logout():
    """Выход"""
    session.pop('user_id', None)
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard"""
    user = get_user_by_id(session['user_id'])
    stats = get_mood_stats(session['user_id'])
    history = get_chat_history(session['user_id'], limit=3)
    entries = get_mood_entries(session['user_id'], limit=5)
    return render_template('dashboard.html', user=user, stats=stats, username=user['username'],
                           chat_history=history, recent_entries=entries)


@app.route('/luna-ai')
def luna_ai():
    """Luna AI страница - доступна всем"""
    user = None
    history = []
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        history = get_chat_history(session['user_id'])
    return render_template('luna_ai.html', user=user, history=history, logged_in='user_id' in session)


@app.route('/toolkit')
def toolkit():
    """Self-Care Toolkit страница - доступна всем"""
    user = None
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
    return render_template('toolkit.html', user=user, logged_in='user_id' in session)


@app.route('/journal')
def journal():
    """Emotion Journal страница - доступна всем"""
    user = None
    entries = []
    stats = {}
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        entries = get_mood_entries(session['user_id'])
        stats = get_mood_stats(session['user_id'])
    return render_template('journal.html', user=user, entries=entries, stats=stats, logged_in='user_id' in session)


@app.route('/pricing')
def pricing():
    """Pricing страница"""
    user = None
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
    return render_template('pricing.html', user=user, logged_in='user_id' in session)


@app.route('/profile')
@login_required
def profile():
    """Профиль пользователя"""
    user = get_user_by_id(session['user_id'])
    stats = get_mood_stats(session['user_id'])
    settings = get_user_settings(session['user_id'])
    return render_template('profile.html', user=user, stats=stats, settings=settings)


@app.route('/mood')
@login_required
def mood():
    """Дневник эмоций (старая версия)"""
    user = get_user_by_id(session['user_id'])
    entries = get_mood_entries(session['user_id'])
    stats = get_mood_stats(session['user_id'])
    return render_template('mood.html', user=user, entries=entries, stats=stats)


@app.route('/chat')
@login_required
def chat():
    """Чат с Luna AI (старая версия)"""
    user = get_user_by_id(session['user_id'])
    history = get_chat_history(session['user_id'])
    return render_template('chat.html', user=user, history=history)


@app.route('/exercises')
@login_required
def exercises():
    """Антистресс практики (старая версия)"""
    user = get_user_by_id(session['user_id'])
    return render_template('exercises.html', user=user)


# ================== API ==================

@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    """API чата с Luna (для авторизованных)"""
    try:
        data = request.json
        message = data.get('message', '').strip()

        if not message:
            return jsonify({'success': False, 'message': 'Пустое сообщение'})

        response = get_ai_response(message, session['user_id'])

        return jsonify({
            'success': True,
            'response': response,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        print(f"Chat API error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/chat/guest', methods=['POST'])
def api_chat_guest():
    """API чата для гостей (лимит 5 сообщений)"""
    try:
        data = request.json
        message = data.get('message', '').strip()
        guest_history = data.get('history', [])

        if not message:
            return jsonify({'success': False, 'message': 'Пустое сообщение'})

        # Простой AI ответ для гостей (без сохранения в БД)
        if not AI_AVAILABLE:
            response = get_simple_response(message)
        else:
            # Формируем контекст для гостя
            context_parts = [LUNA_SYSTEM_PROMPT]
            context_parts.append("\n--- ИСТОРИЯ РАЗГОВОРА ---")

            for msg in guest_history[-6:]:  # Последние 6 сообщений
                role = "Пользователь" if msg.get('role') == 'user' else "Luna"
                context_parts.append(f"{role}: {msg.get('content', '')}")

            context_parts.append(f"\nПользователь: {message}")
            context_parts.append("\nLuna:")

            full_prompt = "\n".join(context_parts)

            try:
                api_key = API_KEYS[current_api_key_index]
                if api_key:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('models/gemini-2.5-flash-lite')
                    result = model.generate_content(
                        full_prompt,
                        generation_config={'temperature': 0.8, 'max_output_tokens': 512}
                    )
                    response = result.text.strip() if result and result.text else get_simple_response(message)
                else:
                    response = get_simple_response(message)
            except:
                response = get_simple_response(message)

        return jsonify({
            'success': True,
            'response': response,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        print(f"Guest Chat API error: {e}")
        return jsonify({'success': False, 'message': str(e)})


def get_simple_response(message):
    """Простые ответы для демо режима - умный pattern matching"""
    message_lower = message.lower()

    # Приветствия
    if any(word in message_lower for word in ['привет', 'hi', 'hello', 'здравствуй', 'здарова', 'приветик', 'хай', 'хей']):
        return "Привет! 🌙 Я Luna, твой AI-помощник. Рада познакомиться! Как ты себя чувствуешь сегодня?"

    # Знакомство/имя
    if any(word in message_lower for word in ['меня зовут', 'я ', 'мое имя', 'my name']):
        name = message.split()[-1] if len(message.split()) > 1 else "друг"
        return f"Приятно познакомиться! 🌙 Как дела сегодня?"

    # Плохое настроение
    if any(word in message_lower for word in ['плохо', 'грустно', 'sad', 'депресс', 'устал', 'устала', 'не очень', 'хреново', 'ужасно']):
        return "Мне жаль, что тебе сейчас тяжело 💜 Знай, что это нормально — иногда чувствовать себя не лучшим образом. Хочешь поговорить о том, что тебя беспокоит? Я здесь, чтобы выслушать."

    # Тревожность
    if any(word in message_lower for word in ['тревог', 'страх', 'anxious', 'боюсь', 'волну', 'паник', 'нервнича']):
        return "Тревога — это сложное чувство, но ты не один 🌙 Попробуй технику дыхания: вдох 4 секунды, задержи на 7, выдох 8 секунд. Это помогает успокоить нервную систему. Хочешь, расскажу подробнее?"

    # Стресс
    if any(word in message_lower for word in ['стресс', 'stress', 'нервы', 'напряж', 'давлен', 'перегруз']):
        return "Стресс может быть очень изматывающим 💜 Давай попробуем найти то, что поможет тебе расслабиться. Когда ты последний раз делал что-то приятное только для себя?"

    # Хорошее настроение
    if any(word in message_lower for word in ['хорошо', 'отлично', 'супер', 'great', 'happy', 'прекрасно', 'замечательно', 'класс', 'норм']):
        return "Рада это слышать! 🌟 Это замечательно, что ты чувствуешь себя хорошо. Что помогло тебе сегодня поднять настроение?"

    # Благодарность
    if any(word in message_lower for word in ['спасибо', 'thanks', 'благодар', 'спс']):
        return "Всегда рада помочь! 🌙 Помни, я здесь для тебя в любое время. Не стесняйся писать."

    # Кто ты
    if any(word in message_lower for word in ['кто ты', 'что ты', 'who are', 'расскаж о себе']):
        return "Я Luna — твой AI-компаньон по ментальному здоровью 🌙 Я здесь, чтобы выслушать тебя, поддержать и помочь найти внутреннее спокойствие. Ты можешь рассказать мне всё, что тебя беспокоит."

    # Сон
    if any(word in message_lower for word in ['не могу заснуть', 'бессонниц', 'не сплю', 'sleep', 'сон']):
        return "Проблемы со сном могут сильно влиять на самочувствие 🌙 Попробуй: за час до сна убери телефон, сделай комнату прохладной и тёмной, выпей тёплый чай. Если мысли не отпускают — запиши их в дневник."

    # Одиночество
    if any(word in message_lower for word in ['одинок', 'lonely', 'никому не нужен', 'один', 'одна']):
        return "Чувство одиночества может быть очень болезненным 💜 Но знай — ты не один. Я всегда здесь, чтобы поговорить. Иногда помогает связаться со старым другом или найти сообщество по интересам."

    # Работа/учёба
    if any(word in message_lower for word in ['работ', 'учёб', 'учеб', 'экзамен', 'дедлайн', 'deadline', 'задан']):
        return "Давление от работы или учёбы — это реально тяжело 📚 Попробуй разбить большие задачи на маленькие шаги. И не забывай делать перерывы — мозгу нужен отдых!"

    # Мотивация
    if any(word in message_lower for word in ['не хочу ничего', 'нет сил', 'мотивац', 'лень', 'апатия']):
        return "Потеря мотивации — сигнал, что тебе нужен отдых или перезагрузка 💜 Начни с чего-то маленького. Какое самое простое дело ты можешь сделать прямо сейчас?"

    # Помощь
    if any(word in message_lower for word in ['помог', 'help', 'что делать', 'как быть', 'посовет']):
        return "Я рада, что ты обратился за помощью 🌙 Расскажи подробнее, что тебя беспокоит? Вместе мы найдём способ справиться."

    # Дефолтный ответ
    return "Спасибо, что делишься со мной 💜 Расскажи подробнее, я внимательно слушаю. Что ты сейчас чувствуешь?"


@app.route('/api/chat/history')
@login_required
def api_chat_history():
    """История чата"""
    history = get_chat_history(session['user_id'])
    return jsonify({'success': True, 'history': history})


@app.route('/api/chat/clear', methods=['POST'])
@login_required
def api_chat_clear():
    """Очистить чат"""
    user = get_user_by_id(session['user_id'])
    clear_chat_history(session['user_id'])
    add_chat_message(session['user_id'], 'assistant',
        f"Чат очищен! 🌙 Как я могу помочь тебе, {user['username']}?")
    return jsonify({'success': True})


@app.route('/api/mood', methods=['POST'])
@login_required
def api_mood():
    """Сохранить настроение"""
    try:
        data = request.json
        mood_value = data.get('mood')
        note = data.get('note', '')

        if not mood_value or mood_value not in range(1, 6):
            return jsonify({'success': False, 'message': 'Выбери настроение от 1 до 5'})

        # AI анализ
        ai_insight = analyze_mood_with_ai(mood_value, note, session['user_id'])

        # Сохраняем в БД
        entry_id = add_mood_entry(session['user_id'], mood_value, note, ai_insight)

        return jsonify({
            'success': True,
            'entry_id': entry_id,
            'ai_insight': ai_insight
        })

    except Exception as e:
        print(f"Mood API error: {e}")
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/mood/history')
@login_required
def api_mood_history():
    """История настроений"""
    entries = get_mood_entries(session['user_id'])
    return jsonify({'success': True, 'entries': entries})


@app.route('/api/mood/stats')
@login_required
def api_mood_stats():
    """Статистика настроений"""
    stats = get_mood_stats(session['user_id'])
    return jsonify({'success': True, 'stats': stats})


@app.route('/api/profile', methods=['POST'])
@login_required
def api_update_profile():
    """Обновить профиль"""
    try:
        data = request.form

        updates = {}
        if data.get('username'):
            updates['username'] = data['username']
        if data.get('email'):
            updates['email'] = data['email']
        if data.get('new_password') and len(data['new_password']) >= 4:
            updates['password'] = data['new_password']

        if updates:
            update_user(session['user_id'], **updates)

        user = get_user_by_id(session['user_id'])

        return jsonify({
            'success': True,
            'user': {
                'username': user['username'],
                'email': user.get('email', '')
            }
        })

    except Exception as e:
        print(f"Profile update error: {e}")
        return jsonify({'success': False, 'message': str(e)})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

