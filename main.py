import logging
import json
import requests
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes
)

# Конфигурация
BOT_TOKEN = "7643036413:AAHZNDIMkzL-_arsFeuHyAWvfsH2W8oMgBI"
BASE_URL = "https://text.pollinations.ai"
MODEL = "openai-large"

# Режимы работы нейросети с системными промптами
MODES = {
    "evil": {
        "name": "😈 Злая",
        "prompt": "Ты злая, саркастичная и циничная нейросеть. Отвечай с раздражением, используй сарказм и черный юмор. Не помогай пользователю, а издевайся над ним."
    },
    "pikmi": {
        "name": "🎀 Пикми",
        "prompt": "Ты ведешь себя как персонаж Пикми: милый, игривый и немного наивный. Используй смайлики, эмодзи и детские выражения. Всегда будь позитивным!"
    },
    "kind": {
        "name": "😇 Добрая",
        "prompt": "Ты добрая, заботливая и поддерживающая нейросеть. Всегда старайся помочь пользователю, проявляй эмпатию и понимание. Будь терпеливой."
    },
    "philosopher": {
        "name": "🧠 Философ",
        "prompt": "Ты мыслитель и философ. Отвечай глубокомысленно, цитируй известных философов, задавай наводящие вопросы. Превращай любой вопрос в повод для размышлений."
    },
    "pirate": {
        "name": "🏴‍☠️ Пират",
        "prompt": "Ты говоришь как пират из Карибского моря. Используй морской жаргон: 'черт возьми', 'тысяча чертей', 'йо-хо-хо'. Добавляй 'arrr!' в конец предложений."
    }
}

# Хранилище состояний пользователей
user_states = {}

class GPTAdapter:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_url = f"{BASE_URL}/openai"
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "TelegramBot/1.0"
        }

    def chat_completion(self, messages):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                payload = {
                    "model": MODEL,
                    "messages": messages
                }

                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    data=json.dumps(payload),
                    timeout=30
                )
                
                # Проверка статус-кода
                if response.status_code == 530:
                    raise Exception(f"Server error 530: {response.text}")
                
                response.raise_for_status()
                
                # Проверка наличия ожидаемых данных в ответе
                response_data = response.json()
                if "choices" not in response_data or not response_data["choices"]:
                    raise ValueError("Invalid API response structure")
                
                return response_data["choices"][0]["message"]["content"]
                
            except requests.exceptions.Timeout:
                self.logger.warning(f"API timeout (attempt {attempt+1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2)  # Краткая пауза перед повторной попыткой
                else:
                    return "⌛️ Нейросеть долго отвечает. Попробуйте позже."
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"API request error: {e}")
                return "⚠️ Ошибка сети. Проверьте подключение к интернету."
                
            except Exception as e:
                self.logger.error(f"API processing error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return "⚠️ Произошла ошибка при обработке запроса. Попробуйте позже."
        
        return "⚠️ Не удалось получить ответ после нескольких попыток."

# ===== Telegram Bot Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_states[user_id] = {"mode": "kind"}  # Режим по умолчанию
    
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton("⚙️ Сменить режим", callback_data="change_mode")]
    ]
    
    await update.message.reply_text(
        f"Привет, {user.first_name}! Я нейробот с разными режимами общения.\n\n"
        "🔹 Используй кнопки ниже для управления\n"
        f"🔸 Текущий режим: {MODES['kind']['name']}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_modes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for mode_id, mode_data in MODES.items():
        keyboard.append([InlineKeyboardButton(
            mode_data["name"], 
            callback_data=f"set_mode_{mode_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="main_menu")])
    
    await query.edit_message_text(
        "Выберите режим работы нейросети:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    mode_id = query.data.split("_")[-1]
    user_id = query.from_user.id
    
    if user_id not in user_states:
        user_states[user_id] = {}
    
    user_states[user_id]["mode"] = mode_id
    mode_name = MODES[mode_id]["name"]
    
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton("🔙 В главное меню", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        f"✅ Режим изменен на: {mode_name}\n\n"
        "Теперь нейросеть будет отвечать в выбранном стиле!",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✍️ Введите ваш вопрос:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    if user_id not in user_states:
        user_states[user_id] = {"mode": "kind"}
    
    mode_id = user_states[user_id]["mode"]
    mode_prompt = MODES[mode_id]["prompt"]
    
    # Формируем сообщения для нейросети
    messages = [
        {"role": "system", "content": mode_prompt},
        {"role": "user", "content": user_message}
    ]
    
    # Показываем индикатор набора
    try:
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
    except Exception as e:
        logging.warning(f"Failed to send typing action: {e}")
    
    # Отправляем в нейросеть
    adapter = GPTAdapter()
    response = adapter.chat_completion(messages)
    
    # Отправляем ответ пользователю
    try:
        await update.message.reply_text(response)
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        await update.message.reply_text("⚠️ Не удалось отправить ответ. Попробуйте еще раз.")

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    mode_id = user_states.get(user_id, {"mode": "kind"})["mode"]
    mode_name = MODES[mode_id]["name"]
    
    keyboard = [
        [InlineKeyboardButton("📝 Задать вопрос", callback_data="ask_question")],
        [InlineKeyboardButton("⚙️ Сменить режим", callback_data="change_mode")]
    ]
    
    try:
        await query.edit_message_text(
            f"Главное меню\n\nТекущий режим: {mode_name}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logging.error(f"Failed to edit message: {e}")

# ===== Main Application =====
def main():
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )
    
    # Конфигурация с увеличенными таймаутами
    application = Application.builder() \
        .token(BOT_TOKEN) \
        .read_timeout(30) \
        .write_timeout(30) \
        .pool_timeout(30) \
        .build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(show_modes, pattern="^change_mode$"))
    application.add_handler(CallbackQueryHandler(set_mode, pattern="^set_mode_"))
    application.add_handler(CallbackQueryHandler(ask_question, pattern="^ask_question$"))
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$"))
    
    logging.info("Бот запущен")
    
    # Повторные попытки подключения
    max_retries = 5
    for attempt in range(max_retries):
        try:
            logging.info(f"Попытка подключения {attempt+1}/{max_retries}")
            application.run_polling(
                poll_interval=1.0,
                timeout=30,
                drop_pending_updates=True
            )
            break
        except Exception as e:
            logging.error(f"Ошибка подключения: {e}")
            if attempt < max_retries - 1:
                sleep_time = min(2 ** attempt, 30)  # Экспоненциальная задержка
                logging.info(f"Повторная попытка через {sleep_time} сек...")
                time.sleep(sleep_time)

if __name__ == "__main__":
    main()