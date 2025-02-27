import os
import asyncio
import datetime
import logging
import re

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters, JobQueue
)

# -----------------------
# Константы и глобальные переменные
# -----------------------
TOKEN = "7650990177:AAGbK924kj-8H7uX13E041kvy78u0vn_WYk"  # Вставь сюда токен от BotFather
ADD_BIRTHDAY = 1  # Состояние ConversationHandler
birthdays = {}    # Словарь для хранения дней рождения (имя -> дата)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------
# Обработчик /start
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветственное сообщение и меню кнопок."""
    reply_keyboard = [
        ["Додати День Народження", "Список Днів Народження"],
        ["Відміна"]
    ]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привет! Я бот-сповіщувач про дні народження.\n"
        "Всі повідомлення українською, але вы можете вводить имена и фамилии "
        "на русском или другом языке.\n\n"
        "Оберіть опцію:",
        reply_markup=markup
    )

# -----------------------
# Начало добавления ДР
# -----------------------
async def add_birthday_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинаем процесс добавления дня рождения."""
    reply_keyboard = [["Відміна"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Введіть дані у форматі: Ім'я мм-дд або Ім'я Прізвище мм-дд\n"
        "Наприклад:\n✅ Оля 04-15\n✅ Андрій Петренко 12-30",
        reply_markup=markup
    )
    return ADD_BIRTHDAY

# -----------------------
# Обработка введённых данных (имя + дата)
# -----------------------
async def add_birthday_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Если пользователь нажал "Відміна"
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

    # Проверка формата мм-дд
    if not re.match(r"^\d{2}-\d{2}$", bday):
        await update.message.reply_text(
            "❌ Помилка! Формат дати має бути мм-дд (наприклад, 04-15)."
        )
        return ADD_BIRTHDAY

    # Проверяем, что дата реальная
    try:
        datetime.datetime.strptime(bday, "%m-%d")
    except ValueError:
        await update.message.reply_text(
            "❌ Некоректна дата. Використовуйте формат мм-дд, наприклад: 04-15"
        )
        return ADD_BIRTHDAY

    # Сохраняем в словарь
    birthdays[name] = bday
    await update.message.reply_text(f"✅ День народження {name} додано!")

    return ConversationHandler.END

# -----------------------
# Список Дней Рождения
# -----------------------
async def list_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выводит список всех сохранённых дней рождения."""
    if not birthdays:
        await update.message.reply_text("📅 Список днів народження порожній.")
    else:
        msg = "📅 Список днів народження:\n"
        for person, date_ in birthdays.items():
            msg += f"{person}: {date_}\n"
        await update.message.reply_text(msg)

# -----------------------
# Напоминание о ДР
# -----------------------
async def birthday_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Проверяем, есть ли сегодня именинники, и рассылаем уведомления."""
    today = datetime.datetime.now().strftime("%m-%d")
    celebrants = [name for name, date_ in birthdays.items() if date_ == today]

    if celebrants:
        message = "🎉 Сьогодні день народження у:\n" + "\n".join(celebrants)
        # Рассылаем всем подписавшимся
        for chat_id in context.bot_data.get("chat_ids", set()):
            try:
                await context.bot.send_message(chat_id=chat_id, text=message)
            except Exception as e:
                logger.error(f"Не вдалося надіслати повідомлення {chat_id}: {e}")

# -----------------------
# Подписка на уведомления (/subscribe)
# -----------------------
async def register_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляем чат в список подписчиков."""
    chat_id = update.message.chat_id
    context.bot_data.setdefault("chat_ids", set()).add(chat_id)
    await update.message.reply_text("✅ Ви підписалися на нагадування про дні народження!")

# -----------------------
# Главная асинхронная функция
# -----------------------
async def main():
    import nest_asyncio
    nest_asyncio.apply()

    # Создаём приложение бота
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler, filters

    app = ApplicationBuilder().token(TOKEN).build()

    # Регистрируем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", register_chat))
    app.add_handler(MessageHandler(filters.Regex("^Список Днів Народження$"), list_birthdays))

    # Кнопка "Відміна"
    app.add_handler(MessageHandler(filters.Regex("^Відміна$"), start))

    # ConversationHandler для добавления ДР
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Додати День Народження$"), add_birthday_start)],
        states={
            ADD_BIRTHDAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_birthday_process)]
        },
        fallbacks=[MessageHandler(filters.Regex("^Відміна$"), start)],
    )
    app.add_handler(conv_handler)

    # Ежедневное напоминание (в 9:00)
    job_queue: JobQueue = app.job_queue
    job_queue.run_daily(birthday_reminder, time=datetime.time(hour=9, minute=0))

    # Запускаем бота (polling)
    await app.run_polling()

# -----------------------
# Точка входа
# -----------------------
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())



      
