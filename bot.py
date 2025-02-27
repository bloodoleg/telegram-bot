import logging
import re
import datetime
import nest_asyncio
import threading

from flask import Flask
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters, JobQueue
)

TOKEN = "7650990177:AAGbK924kj-8H7uX13E041kvy78u0vn_WYk"

# Flask-заглушка, чтобы Render видел веб-сервис
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот працює 24/7 на Render!"

birthdays = {}   # имя -> дата (мм-дд)
ADD_BIRTHDAY = 1 # состояние ConversationHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Обработчик /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [
        ["Додати День Народження", "Список Днів Народження"],
        ["Відміна"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привіт! Я бот-сповіщувач про дні народження.\n"
        "Всі повідомлення українською, але ви можете вводити імена та прізвища\n"
        "російською або іншою мовою.\n\n"
        "Оберіть опцію:",
        reply_markup=markup
    )

# Начало добавления ДР
async def add_birthday_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [["Відміна"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Введіть дані у форматі: Ім'я мм-дд або Ім'я Прізвище мм-дд\n"
        "Наприклад:\n✅ Оля 04-15\n✅ Андрій Петренко 12-30",
        reply_markup=markup
    )
    return ADD_BIRTHDAY

# Обработка (имя + дата)
async def add_birthday_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Відміна":
        await start(update, context)
        return ConversationHandler.END

    parts = text.rsplit(" ", 1)
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ Неправильний формат! Використовуйте формат:\n"
            "Ім'я мм-дд або Ім'я Прізвище мм-дд\n"
            "Наприклад:\n✅ Оля 04-15\n✅ Андрій Петренко 12-30"
        )
        return ADD_BIRTHDAY

    name, bday = parts

    if not re.match(r"^\d{2}-\d{2}$", bday):
        await update.message.reply_text(
            "❌ Помилка! Формат дати має бути мм-дд (наприклад, 04-15)."
        )
        return ADD_BIRTHDAY

    try:
        datetime.datetime.strptime(bday, "%m-%d")
    except ValueError:
        await update.message.reply_text(
            "❌ Некоректна дата. Використовуйте формат мм-дд, наприклад: 04-15"
        )
        return ADD_BIRTHDAY

    birthdays[name] = bday
    await update.message.reply_text(f"✅ День народження {name} додано!")
    return ConversationHandler.END

# Список всех ДР
async def list_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not birthdays:
        await update.message.reply_text("📅 Список днів народження порожній.")
    else:
        msg = "📅 Список днів народження:\n"
        for person, date_ in birthdays.items():
            msg += f"{person}: {date_}\n"
        await update.message.reply_text(msg)

# Ежедневное напоминание
async def birthday_reminder(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.datetime.now().strftime("%m-%d")
    celebrants = [name for name, date_ in birthdays.items() if date_ == today]
    if celebrants:
        message = "🎉 Сьогодні день народження у:\n" + "\n".join(celebrants)
        for chat_id in context.bot_data.get("chat_ids", set()):
            try:
                await context.bot.send_message(chat_id=chat_id, text=message)
            except Exception as e:
                logger.error(f"Не вдалося надіслати повідомлення {chat_id}: {e}")

# /subscribe — подписка на уведомления
async def register_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    context.bot_data.setdefault("chat_ids", set()).add(chat_id)
    await update.message.reply_text("✅ Ви підписалися на нагадування про дні народження!")

# Запуск Telegram-бота в дочернем потоке
def run_telegram_bot():
    nest_asyncio.apply()

    from telegram.ext import (
        ApplicationBuilder, CommandHandler, MessageHandler,
        ConversationHandler, filters
    )

    app_telegram = ApplicationBuilder().token(TOKEN).build()

    # Регистрируем команды
    app_telegram.add_handler(CommandHandler("start", start))
    app_telegram.add_handler(CommandHandler("subscribe", register_chat))
    app_telegram.add_handler(MessageHandler(filters.Regex("^Список Днів Народження$"), list_birthdays))
    app_telegram.add_handler(MessageHandler(filters.Regex("^Відміна$"), start))

    # ConversationHandler для добавления ДР
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Додати День Народження$"), add_birthday_start)],
        states={
            1: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_birthday_process)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Відміна$"), start)],
    )
    app_telegram.add_handler(conv_handler)

    # Ежедневное напоминание о 9:00
    job_queue: JobQueue = app_telegram.job_queue
    job_queue.run_daily(birthday_reminder, time=datetime.time(hour=9, minute=0))

    logger.info("Запускаю long polling без сигналов...")
    # ОТКЛЮЧАЕМ обработку сигналов, чтобы не было ошибки set_wakeup_fd
    app_telegram.run_polling(stop_signals=None)

# Запускаем бота (polling) в потоке
threading.Thread(target=run_telegram_bot, daemon=True).start()

# Запуск Flask (в главном потоке)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
