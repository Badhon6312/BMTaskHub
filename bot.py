
import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ["BOT_TOKEN"]

def init_db():
    with sqlite3.connect("tasks.db") as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                role TEXT NOT NULL
            )
        """)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("👷 Worker", callback_data="worker")],
        [InlineKeyboardButton("💼 Client", callback_data="client")]
    ]
    await update.message.reply_text(
        "🦊 Welcome to BMTaskHub!\nতুমি কোন অ্যাকাউন্ট তৈরি করতে চাও?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    role = query.data
    user = query.from_user

    with sqlite3.connect("tasks.db") as con:
        con.execute("""
            INSERT INTO users (telegram_id, username, role)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                role=excluded.role
        """, (user.id, user.username or "", role))

    await query.edit_message_text(
        f"✅ Registration successful! Account: {role.title()}"
    )

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(
        choose_role, pattern="^(worker|client)$"
    ))
    app.run_polling()

if __name__ == "__main__":
    main()
