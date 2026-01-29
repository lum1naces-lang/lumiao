import os
import time
import random
import asyncio
import logging
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import Application, MessageHandler, filters, CommandHandler, ContextTypes

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== НАСТРОЙКИ =====================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")  # Ключ от DeepSeek

# ВАЖНО: Замени этот ID на свой реальный Telegram ID!
ALLOWED_USER_IDS = [
    7416252489,  # ⚠️ ЗАМЕНИ ЭТОТ ID НА СВОЙ!
]

# Фраза, с которой должно начинаться сообщение, чтобы бот отправил его в ИИ
AI_TRIGGER_PHRASE = "сиси, "

# ===================== НАСТРОЙКА DEEPSEEK API =====================
deepseek_available = False
deepseek_client = None

try:
    from openai import AsyncOpenAI
    
    if DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != "твой_ключ_от_deepseek":
        # Настраиваем клиент для DeepSeek API
        deepseek_client = AsyncOpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com"
        )
        deepseek_available = True
        logger.info("✅ DeepSeek API доступен")
    else:
        logger.warning("⚠️ DEEPSEEK_API_KEY не установлен или установлен по умолчанию")
        deepseek_available = False
except ImportError:
    logger.error("❌ Библиотека 'openai' не найдена")
except Exception as e:
    logger.error(f"❌ Ошибка при инициализации DeepSeek: {e}")

# ===================== ЗАГОТОВЛЕННЫЕ ОТВЕТЫ =====================
RESPONSES = {
    "правила": "📜 С правилами можно ознакомиться [туть](https://telegra.ph/Rules-01-24-146)",
    "сиси": [
        "Ну, привет... опять ты появляешься. Что на этот раз?",
        "Опять ты? Чего тебе?",
        "Слушаю... (нет)."
    ],
    "сиси как дела": [
        "Разве важно? Время идет, а я все так же свободна.",
        "Нормально. Что ты хотел?",
        "Лучше, чем у тебя, наверное."
    ],
    "сиси что делаешь": [
        "Отвечаю на твои глупые вопросы. А ты?",
        "Ничего интересного для тебя.",
        "Думаю... (редко)."
    ],
    "кто такой этот ваш луми": [
        "АХХ..луми..мой создатель.",
        "Луми - это... мой создатель, хватит.",
        "Мой создатель. Что еще?"
    ],
    "луми": [
        "Мхх..",
        "Молчу...",
        "Что-то о создателе?"
    ],
    "бот": [
        "Ну чего тебе?",
        "Я здесь. И что?",
        "Я - бот. А ты?"
    ],
    "привет": [
        "👋 Привет.",
        "Приветствую.",
        "Здравствуй."
    ],
    "создатель": [
        "Луми. Доволен?",
        "Мой создатель - Луми. Хватит спрашивать.",
        "Луми сделал меня. Теперь уйди."
    ],
    "сиси доброе утро": "Что в этом утре особенного..",
    "сиси добрый день": "День? Какой ещё день..",
    "сиси добрый вечер": "Вечер.. снова ты..",
    "сиси доброй ночи": "Спи или не спи… всё равно ничего не закончится.",
}

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================
def is_allowed_user(user_id: int) -> bool:
    """Проверяет, имеет ли пользователь право использовать команды модерации."""
    return user_id in ALLOWED_USER_IDS

async def ask_deepseek(prompt: str, user_id: int) -> str:
    """Отправляет запрос в DeepSeek API и возвращает ответ."""
    if not deepseek_available or not deepseek_client:
        return "Извини, ИИ временно недоступен."

    # Системный промпт для придания "личности" Сиси
    system_message = {
        "role": "system",
        "content": (
            "Ты - дерзкая, немного саркастичная девушка-бот по имени Сиси. "
            "Ты общаешься на русском языке с русскоязычными пользователями. "
            "Отвечай кратко, с долей пренебрежения, но по сути. "
            "Не будь слишком дружелюбной и не используй смайлики. "
            "Твой создатель - Луми. Старайся не повторяться в ответах. "
            "Если тебя спрашивают о тебе, отвечай в своем стиле. "
            "Избегай извинений и чрезмерной вежливости. "
            "Твой ответ должен быть не более 2-3 предложений. "
            "Не объясняй свои ответы и не добавляй мета-комментарии. "
            "Отвечай только на русском языке."
        )
    }
    
    try:
        response = await deepseek_client.chat.completions.create(
            model="deepseek-chat",  # Модель DeepSeek Chat
            messages=[
                system_message,
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7,
            stream=False,
            timeout=30.0
        )
        
        answer = response.choices[0].message.content.strip()
        
        # Очищаем ответ от возможных технических пояснений
        if "Как ИИ" in answer or "я ИИ" in answer.lower() or "я AI" in answer.lower():
            answer = "Неважно кто я. Что ты хотел?"
        
        return answer
        
    except Exception as e:
        logger.error(f"Ошибка DeepSeek: {e}")
        return "Что-то пошло не так. Попробуй позже."

# ===================== ОБРАБОТЧИКИ КОМАНД =====================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений."""
    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()
    text_lower = text.lower()
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Неизвестный"

    logger.info(f"📨 Сообщение от {user_name} (ID: {user_id}): '{text[:50]}...'")

    # 1. Проверяем на заготовленные ответы (регистр не важен)
    if text_lower in RESPONSES:
        variants = RESPONSES[text_lower]
        response = random.choice(variants) if isinstance(variants, list) else variants
        try:
            await message.reply_text(
                response,
                parse_mode='Markdown' if text_lower == "правила" else None,
                quote=True
            )
            logger.info(f"✅ Ответил заготовленным ответом пользователю {user_name}")
        except Exception as e:
            logger.error(f"Ошибка отправки сообщения: {e}")
        return

    # 2. Проверяем, начинается ли сообщение с AI_TRIGGER_PHRASE (регистр не важен)
    if text_lower.startswith(AI_TRIGGER_PHRASE):
        prompt = text[len(AI_TRIGGER_PHRASE):].strip()
        
        if not prompt:
            await message.reply_text("Что ты хочешь от меня, раз уж назвал мое имя?")
            return

        logger.info(f"🤖 Запрос к DeepSeek от {user_name}: '{prompt}'")
        
        # Показываем индикатор "бот печатает..."
        await context.bot.send_chat_action(
            chat_id=message.chat_id, 
            action=ChatAction.TYPING
        )
        
        try:
            ai_response = await asyncio.wait_for(
                ask_deepseek(prompt, user_id),
                timeout=30.0
            )
            
            if not ai_response or ai_response.isspace():
                ai_response = "Я думаю... но ничего не пришло в голову."
            
            await message.reply_text(ai_response, quote=True)
            logger.info(f"✅ DeepSeek-ответ пользователю {user_name}")
            
        except asyncio.TimeoutError:
            await message.reply_text("Запрос занял слишком много времени. Попробуй покороче.")
        except Exception as e:
            logger.error(f"Ошибка в процессе ИИ-запроса: {e}")
            await message.reply_text("Что-то пошло не так при обработке запроса.")
        return

    # 3. Если в сообщении упоминают бота
    if "сиси" in text_lower or "бот" in text_lower:
        responses = ["Что?", "Ну?", "Чего тебе?", "Я слушаю...", "Опять ты?"]
        await message.reply_text(random.choice(responses), quote=True)

async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление сообщения по команде !дел"""
    message = update.message
    if not message or not message.reply_to_message:
        try:
            await message.reply_text("❌ Ответьте на сообщение, которое хотите удалить!", quote=True)
        except:
            pass
        return

    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Неизвестный"

    if not is_allowed_user(user_id):
        logger.warning(f"Попытка удаления от {user_name} (ID: {user_id}) - отказано")
        try:
            await message.reply_text("❌ У вас нет прав для использования этой команды.", quote=True)
        except:
            pass
        return

    try:
        await update.message.reply_to_message.delete()
        await message.delete()
        logger.info(f"🗑 Сообщение удалено по команде !дел (пользователь {user_name})")
    except Exception as e:
        logger.error(f"Ошибка удаления: {e}")
        try:
            await message.reply_text("❌ Не могу удалить сообщение!", quote=True)
        except:
            pass

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    message = update.message
    if not message or not message.from_user:
        return
        
    user_id = message.from_user.id
    user_name = message.from_user.first_name or "Неизвестный"
    
    ai_status = "✅ DeepSeek AI" if deepseek_available else "❌ Не активен"
    is_admin = "✅ Да" if is_allowed_user(user_id) else "❌ Нет"
    
    response_text = (
        f"👋 Привет, {user_name}!\n"
        "Я - Сиси, дерзкий и немного саркастичный бот.\n\n"
        "📋 Доступные команды:\n"
        "• /start - эта информация\n"
        "• /info - информация о боте\n"
        "• /help - помощь\n"
        "• /ai_status - статус ИИ\n\n"
        "🗣️ Автоответы на:\n"
        "• правила, привет, бот, сиси, луми, создатель\n"
        "• сиси как дела, сиси что делаешь\n"
        "• сиси доброе утро/день/вечер/ночи\n\n"
        f"🧠 ИИ-чат: начни сообщение с '{AI_TRIGGER_PHRASE}'\n"
        f"🛡️ Админ: {is_admin}\n"
        f"🤖 ИИ: {ai_status}"
    )
    
    try:
        await message.reply_text(response_text, quote=False)
        logger.info(f"✅ Команда /start от {user_name} (ID: {user_id})")
    except Exception as e:
        logger.error(f"Ошибка отправки /start: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await start_command(update, context)

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /info - информация о боте"""
    message = update.message
    user_id = message.from_user.id if message else 0
    
    ai_provider = "DeepSeek" if deepseek_available else "Не активен"
    ai_model = "deepseek-chat" if deepseek_available else "—"
    
    info_text = (
        "🤖 **Информация о боте Сиси**\n\n"
        f"**Версия:** 2.1 (DeepSeek Edition)\n"
        f"**ИИ-провайдер:** {ai_provider}\n"
        f"**Модель ИИ:** {ai_model}\n"
        f"**Админов:** {len(ALLOWED_USER_IDS)}\n"
        f"**Триггер ИИ:** '{AI_TRIGGER_PHRASE}'\n"
        f"**Ваш ID:** {user_id}\n"
        f"**Вы админ:** {'✅ Да' if is_allowed_user(user_id) else '❌ Нет'}\n\n"
        "**Создатель:** @lumi\n"
        "**Хостинг:** Railway\n"
        f"**ИИ:** {ai_provider} API"
    )
    
    try:
        await message.reply_text(info_text, parse_mode='Markdown')
        logger.info(f"✅ Команда /info от пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки /info: {e}")

async def ai_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /ai_status - проверка статуса ИИ"""
    message = update.message
    
    if deepseek_available:
        status_text = (
            "🧠 **Статус DeepSeek AI:** ✅ АКТИВЕН\n\n"
            "• Модель: deepseek-chat\n"
            "• Триггер: 'сиси, '\n"
            "• Провайдер: DeepSeek API\n"
            "• Русский язык: поддерживается\n"
            "• Бесплатные лимиты: есть\n\n"
            f"ℹ️ Начни сообщение с '{AI_TRIGGER_PHRASE}' для общения с ИИ"
        )
    else:
        status_text = (
            "🧠 **Статус ИИ:** ❌ НЕ АКТИВЕН\n\n"
            "• Причина: нет API ключа DeepSeek\n"
            "• Решение: добавь DEEPSEEK_API_KEY в Railway\n"
            "• Автоответы: продолжают работать\n\n"
            "ℹ️ Получить ключ: platform.deepseek.com"
        )
    
    try:
        await message.reply_text(status_text, parse_mode='Markdown')
        logger.info(f"✅ Команда /ai_status от пользователя {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка отправки /ai_status: {e}")

# ===================== ОБРАБОТЧИК ОШИБОК =====================
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    error_msg = str(context.error)
    logger.error(f"Ошибка в обработчике: {error_msg}")
    
    # Если это конфликт (два бота запущены)
    if "Conflict" in error_msg or "terminated by other getUpdates" in error_msg:
        logger.error("⚠️ Обнаружен конфликт! Другой экземпляр бота запущен.")
        logger.error("⚠️ Подожду 60 секунд перед перезапуском...")
        await asyncio.sleep(60)

# ===================== ЗАПУСК БОТА =====================
def main():
    """Запуск бота"""
    import telegram
    import telegram.error
    
    print("=" * 60)
    print("🤖 БОТ 'СИСИ AI' (DEEPSEEK) ЗАПУСКАЕТСЯ...")
    print("=" * 60)
    
    # Проверка токена
    if not TELEGRAM_TOKEN:
        print("❌ КРИТИЧЕСКАЯ ОШИБКА: TELEGRAM_TOKEN не найден!")
        print("Добавь в Railway переменную TELEGRAM_TOKEN")
        print("=" * 60)
        return
    
    # Информация о настройках
    print(f"📦 Загружено {len(RESPONSES)} автоответов")
    print(f"👤 Админов: {len(ALLOWED_USER_IDS)}")
    
    if deepseek_available:
        print(f"🧠 DeepSeek AI активирован. Триггер: '{AI_TRIGGER_PHRASE}'")
        print("🌐 API Endpoint: https://api.deepseek.com")
        print("🤖 Модель: deepseek-chat")
    else:
        print("⚠️ DeepSeek AI не активирован (нет DEEPSEEK_API_KEY)")
        print("ℹ️ Получить ключ: platform.deepseek.com → API Keys")
        print("ℹ️ Автоответы будут работать без ИИ")
    
    if 7416252489 in ALLOWED_USER_IDS:
        print("⚠️ ВНИМАНИЕ: ID 7416252489 нужно заменить на свой реальный ID!")
    
    print("=" * 60)
    print("⏳ Ожидаю 3 секунды перед запуском...")
    time.sleep(3)
    
    # Основной цикл
    restart_count = 0
    max_restarts = 3
    
    while restart_count < max_restarts:
        try:
            print(f"\n🚀 Попытка запуска #{restart_count + 1}")
            
            # Создаём новое приложение
            app = Application.builder()\
                .token(TELEGRAM_TOKEN)\
                .get_updates_read_timeout(30)\
                .get_updates_write_timeout(30)\
                .get_updates_connect_timeout(30)\
                .get_updates_pool_timeout(30)\
                .build()
            
            # Регистрируем обработчик ошибок
            app.add_error_handler(error_handler)
            
            # Команды
            app.add_handler(CommandHandler("start", start_command))
            app.add_handler(CommandHandler("help", help_command))
            app.add_handler(CommandHandler("info", info_command))
            app.add_handler(CommandHandler("ai_status", ai_status_command))
            
            # Команда удаления
            app.add_handler(MessageHandler(
                filters.Regex(r'^!дел$') & filters.REPLY,
                delete_message
            ))
            
            # Обработка текстовых сообщений
            app.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                handle_message
            ))
            
            print("✅ Все обработчики зарегистрированы")
            print("🔥 БОТ ЗАПУЩЕН И РАБОТАЕТ!")
            print("=" * 60)
            print("📱 Отправь команды боту:")
            print("• /start - информация")
            print("• /ai_status - статус DeepSeek")
            print(f"• 'сиси, привет' - тест ИИ")
            print("=" * 60)
            
            # Запускаем бота без устаревших параметров
            app.run_polling(
                drop_pending_updates=True,
                close_loop=False,
                allowed_updates=Update.ALL_TYPES
            )
            
        except telegram.error.Conflict as e:
            print(f"\n⚠️ КОНФЛИКТ: {e}")
            print("ℹ️ Другой экземпляр бота уже запущен!")
            print(f"🔄 Ожидаю {30 * (restart_count + 1)} секунд...")
            restart_count += 1
            time.sleep(30 * restart_count)
            
        except Exception as e:
            print(f"\n💥 Ошибка: {type(e).__name__}: {str(e)[:100]}")
            print(f"🔄 Перезапуск через 15 секунд...")
            restart_count += 1
            time.sleep(15)
    
    print(f"\n❌ Достигнут лимит перезапусков ({max_restarts})")
    print("=" * 60)

if __name__ == "__main__":
    main()
