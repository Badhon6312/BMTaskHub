
import os
import json
import sqlite3
import urllib.request
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
PUBLIC_URL = os.environ.get(
    "PUBLIC_URL", "https://bm-task-hub.onrender.com"
)
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BMTaskHub</title>
<style>
body {
  background: #101014;
  color: white;
  font-family: Arial, sans-serif;
  text-align: center;
  padding: 35px 15px;
}
.card {
  max-width: 480px;
  margin: 30px auto;
  padding: 28px;
  background: #19171d;
  border: 1px solid #39313b;
  border-radius: 22px;
}
p { color: #bbb; line-height: 1.7; }
a {
  display: inline-block;
  padding: 14px 22px;
  background: #ff793d;
  color: white;
  text-decoration: none;
  border-radius: 12px;
}
</style>
</head>
<body>
<div class="card">
  <h1>🦊 BMTaskHub</h1>
  <p>Find tasks. Complete tasks. Earn rewards.</p>
  <p>💼 Client — Post tasks</p>
  <p>👷 Worker — Complete tasks</p>
  <a href="https://t.me/YOUR_BOT_USERNAME">
    Open Telegram Bot
  </a>
</div>
</body>
</html>
"""


def telegram_api(method, data):
    if not TOKEN:
        return {}

    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    payload = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def init_db():
    with sqlite3.connect("tasks.db") as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                role TEXT NOT NULL
            )
        """)


def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = keyboard
    telegram_api("sendMessage", data)


@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/telegram-webhook", methods=["POST"])
def telegram_webhook():
    if WEBHOOK_SECRET:
        supplied = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token", ""
        )
        if supplied != WEBHOOK_SECRET:
            return jsonify({"error": "Unauthorized"}), 403

    update = request.get_json(silent=True) or {}

    message = update.get("message")
    if message:
        text = message.get("text", "")
        chat_id = message["chat"]["id"]

        if text.startswith("/start"):
            keyboard = {
                "inline_keyboard": [
                    [{
                        "text": "👷 Worker",
                        "callback_data": "worker"
                    }],
                    [{
                        "text": "💼 Client",
                        "callback_data": "client"
                    }]
                ]
            }
            send_message(
                chat_id,
                "🦊 Welcome to BMTaskHub!\\n"
                "তুমি কোন অ্যাকাউন্ট তৈরি করতে চাও?",
                keyboard
            )

    callback = update.get("callback_query")
    if callback:
        query_id = callback["id"]
        role = callback.get("data", "")
        user = callback.get("from", {})
        chat_id = callback["message"]["chat"]["id"]

        if role in ("worker", "client"):
            with sqlite3.connect("tasks.db") as con:
                con.execute("""
                    INSERT INTO users (telegram_id, username, role)
                    VALUES (?, ?, ?)
                    ON CONFLICT(telegram_id) DO UPDATE SET
                    username=excluded.username,
                    role=excluded.role
                """, (
                    user.get("id"),
                    user.get("bmtaskhub_bot", ""),
                    role
                ))

            telegram_api("answerCallbackQuery", {
                "callback_query_id": query_id,
                "text": "Registration successful!"
            })
            send_message(
                chat_id,
                "✅ Registration successful!\\n"
                f"Account: {role.title()}"
            )

    return jsonify({"ok": True})


def set_webhook():
    if TOKEN and PUBLIC_URL:
        try:
            data = {
                "url": PUBLIC_URL.rstrip("/") + "/telegram-webhook"
            }
            if WEBHOOK_SECRET:
                data["secret_token"] = WEBHOOK_SECRET
            telegram_api("setWebhook", data)
        except Exception as error:
            print("Webhook setup failed:", error)


init_db()
set_webhook()
