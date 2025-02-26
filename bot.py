

import os
import asyncio
import datetime
import logging
import re

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          ConversationHandler, ContextTypes, filters, JobQueue)
from flask import Flask
from threading import Thread

app_flask = Flask(__name__)


@app_flask.route('/')
def home():
    return "Бот працює 24/7"



birthdays = {}
ADD_BIRTHDAY = 1

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Твой токен вставлен сюда
TOKEN = "7650990177:AAGbK924kj-8H7uX13E041kvy78u0vn_WYk"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [["Додати День Народження", "Список Днів Народження"],
                      ["Відміна"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Привіт! Я бот-сповіщувач про дні народження.\n"
        "Всі повідомлення українською, але ви можете вводити імена "
        "та прізвища російською або іншою мовою.\n\n"
        "Оберіть опцію:",
        reply_markup=markup)


async def add_birthday_start(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [["Відміна"]]
    markup = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Введіть дані у форматі: Ім'я мм-дд або Ім'я Прізвище мм-дд\n"
        "Наприклад:\n✅ Оля 04-15\n✅ Андрій Петренко 12-30",
        reply_markup=markup)
    return ADD_BIRTHDAY


async def add_birthday_process(update: Update,
                               context: ContextTypes.DEFAULT_TYPE):
    print("=== add_birthday_process викликана! ===")
    text = update.message.text

    if text == "Відміна":
        await start(update, context)
        return ConversationHandler.END

    parts = text.rsplit(" ", 1)
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ Неправильний формат! Використовуйте формат:\n"
            "Ім'я мм-дд або Ім'я Прізвище мм-дд\n"
            "Наприклад:\n✅ Оля 04-15\n✅ Андрій Петренко 12-30")
        return ADD_BIRTHDAY

    name, bday = parts

    if not re.match(r"^\d{2}-\d{2}$", bday):
        await update.message.reply_text(
            "❌ Помилка! Формат дати має бути мм-дд (наприклад, 04-15).")
        return ADD_BIRTHDAY

    try:
        datetime.datetime.strptime(bday, "%m-%d")
    except ValueError:
        await update.message.reply_text(
            "❌ Некоректна дата. Використовуйте формат мм-дд, наприклад: 04-15")
        return ADD_BIRTHDAY

    birthdays[name] = bday
    await update.message.reply_text(f"✅ День народження {name} додано!")
    return ConversationHandler.END


async def list_birthdays(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not birthdays:
        await update.message.reply_text("📅 Список днів народження порожній.")
    else:
        msg = "📅 Список днів народження:\n" + "\n".join(
            f"{name}: {date_}" for name, date_ in birthdays.items())
        await update.message.reply_text(msg)


async def birthday_reminder(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.datetime.now().strftime("%m-%d")
    celebrants = [name for name, date_ in birthdays.items() if date_ == today]
    if celebrants:
        message = "🎉 Сьогодні день народження у:\n" + "\n".join(celebrants)
        for chat_id in context.bot_data.get("chat_ids", set()):
            try:
                await context.bot.send_message(chat_id=chat_id, text=message)
            except Exception as e:
                logging.error(
                    f"Не вдалося надіслати повідомлення {chat_id}: {e}")


async def register_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    context.bot_data.setdefault("chat_ids", set()).add(chat_id)
    await update.message.reply_text(
        "✅ Ви підписалися на нагадування про дні народження!")


async def main():
    import nest_asyncio
    nest_asyncio.apply()

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.Regex("^Список Днів Народження$"),
                       list_birthdays))
    app.add_handler(MessageHandler(filters.Regex("^Відміна$"), start))
    app.add_handler(CommandHandler("subscribe", register_chat))

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^Додати День Народження$"),
                           add_birthday_start)
        ],
        states={
            ADD_BIRTHDAY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND,
                               add_birthday_process)
            ]
        },
        fallbacks=[MessageHandler(filters.Regex("^Відміна$"), start)],
    )
    app.add_handler(conv_handler)

    job_queue: JobQueue = app.job_queue
    job_queue.run_daily(birthday_reminder,
                        time=datetime.time(hour=9, minute=0))

    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
