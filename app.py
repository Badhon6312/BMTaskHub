
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
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0") or "0")
DB_PATH = os.environ.get("DB_PATH", "tasks.db")

BOT_URL = "https://t.me/bmtaskhub_bot"


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
p {
  color: #bbb;
  line-height: 1.7;
}
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
  <a href="https://t.me/bmtaskhub_bot">Open Telegram Bot</a>
</div>
</body>
</html>
"""


def connect_db():
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with connect_db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            role TEXT NOT NULL
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            reward REAL NOT NULL,
            slots INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            worker_id INTEGER NOT NULL,
            proof TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'working',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(task_id, worker_id)
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS states (
            telegram_id INTEGER PRIMARY KEY,
            state TEXT NOT NULL,
            data TEXT NOT NULL DEFAULT '{}'
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS balances (
            telegram_id INTEGER PRIMARY KEY,
            amount REAL NOT NULL DEFAULT 0
        )
        """)


def telegram_api(method, data):
    if not TOKEN:
        print("BOT_TOKEN is missing.")
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
        result = json.loads(response.read().decode("utf-8"))

    if not result.get("ok"):
        print("Telegram API error:", result.get("description"))

    return result


def send_message(chat_id, text, keyboard=None):
    data = {"chat_id": chat_id, "text": text}

    if keyboard:
        data["reply_markup"] = keyboard

    try:
        telegram_api("sendMessage", data)
    except Exception as exc:
        print("Message sending failed:", exc)


def make_keyboard(rows):
    return {"inline_keyboard": rows}


def set_state(user_id, state, data=None):
    with connect_db() as con:
        con.execute("""
        INSERT INTO states (telegram_id, state, data)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
        state=excluded.state,
        data=excluded.data
        """, (user_id, state, json.dumps(data or {})))


def get_state(user_id):
    with connect_db() as con:
        row = con.execute(
            "SELECT state, data FROM states WHERE telegram_id=?",
            (user_id,)
        ).fetchone()

    if not row:
        return None, {}

    return row["state"], json.loads(row["data"])


def clear_state(user_id):
    with connect_db() as con:
        con.execute(
            "DELETE FROM states WHERE telegram_id=?",
            (user_id,)
        )


def get_role(user_id):
    with connect_db() as con:
        row = con.execute(
            "SELECT role FROM users WHERE telegram_id=?",
            (user_id,)
        ).fetchone()

    return row["role"] if row else None


def register_user(user, role):
    user_id = user.get("id")

    with connect_db() as con:
        con.execute("""
        INSERT INTO users (telegram_id, username, role)
        VALUES (?, ?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET
        username=excluded.username,
        role=excluded.role
        """, (user_id, user.get("username", ""), role))

        con.execute("""
        INSERT OR IGNORE INTO balances (telegram_id, amount)
        VALUES (?, 0)
        """, (user_id,))


def main_menu(chat_id, user_id):
    role = get_role(user_id)

    if role == "client":
        keyboard = make_keyboard([
            [{"text": "➕ Post Task", "callback_data": "post"}],
            [{"text": "📋 My Tasks", "callback_data": "mytasks"}]
        ])
        send_message(chat_id, "💼 Client Menu", keyboard)

    elif role == "worker":
        keyboard = make_keyboard([
            [{"text": "🔎 Browse Tasks", "callback_data": "browse"}],
            [{"text": "📋 My Submissions", "callback_data": "mysub"}],
            [{"text": "💰 Test Balance", "callback_data": "balance"}]
        ])
        send_message(chat_id, "👷 Worker Menu", keyboard)

    else:
        send_message(chat_id, "আগে /start দিয়ে অ্যাকাউন্ট তৈরি করো।")


def create_task_step(chat_id, user_id, text, state, data):
    if state == "title":
        if not text or len(text) > 100:
            send_message(chat_id, "শিরোনাম ১–১০০ অক্ষরের মধ্যে লেখো।")
            return

        data["title"] = text
        set_state(user_id, "description", data)
        send_message(
            chat_id,
            "Task-এর বিস্তারিত বর্ণনা লেখো (সর্বোচ্চ ১০০০ অক্ষর)।"
        )

    elif state == "description":
        if not text or len(text) > 1000:
            send_message(chat_id, "বর্ণনা ১–১০০০ অক্ষরের মধ্যে লেখো।")
            return

        data["description"] = text
        set_state(user_id, "reward", data)
        send_message(
            chat_id,
            "প্রতি Task-এর পরীক্ষামূলক Reward কত BDT? শুধু সংখ্যা লেখো, যেমন 10"
        )

    elif state == "reward":
        try:
            reward = float(text)
            if not 0 < reward <= 10000:
                raise ValueError
        except (ValueError, TypeError):
            send_message(chat_id, "১ থেকে ১০,০০০-এর মধ্যে সঠিক সংখ্যা লেখো।")
            return

        data["reward"] = reward
        set_state(user_id, "slots", data)
        send_message(
            chat_id,
            "কতজন Worker কাজটি করতে পারবে? ১–১০০০-এর মধ্যে পূর্ণসংখ্যা লেখো।"
        )

    elif state == "slots":
        try:
            slots = int(text)
            if not 1 <= slots <= 1000:
                raise ValueError
        except (ValueError, TypeError):
            send_message(chat_id, "১ থেকে ১০০০-এর মধ্যে পূর্ণসংখ্যা লেখো।")
            return

        data["slots"] = slots

        with connect_db() as con:
            con.execute("""
            INSERT INTO tasks
            (client_id, title, description, reward, slots, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            """, (
                user_id,
                data["title"],
                data["description"],
                data["reward"],
                data["slots"]
            ))

        clear_state(user_id)
        send_message(
            chat_id,
            "✅ Task জমা হয়েছে। Admin অনুমোদন করলে Worker-রা দেখতে পারবে।"
        )
        main_menu(chat_id, user_id)


def browse_tasks(chat_id):
    with connect_db() as con:
        tasks = con.execute("""
        SELECT id, title, description, reward, slots
        FROM tasks
        WHERE status='approved' AND slots > 0
        ORDER BY id DESC LIMIT 10
        """).fetchall()

    if not tasks:
        send_message(chat_id, "এখন কোনো অনুমোদিত Task নেই।")
        return

    for task in tasks:
        message = (
            f"📝 {task['title']}\n"
            f"{task['description']}\n"
            f"Reward: {task['reward']} BDT (TEST ONLY)\n"
            f"Available slots: {task['slots']}"
        )

        keyboard = make_keyboard([[
            {
                "text": "আমি কাজটি করব",
                "callback_data": f"claim:{task['id']}"
            }
        ]])

        send_message(chat_id, message, keyboard)


def admin_panel(chat_id, user_id):
    if not ADMIN_ID or user_id != ADMIN_ID:
        send_message(chat_id, "⛔ Admin access নেই।")
        return

    with connect_db() as con:
        tasks = con.execute("""
        SELECT id, title, reward, slots
        FROM tasks
        WHERE status='pending'
        ORDER BY id LIMIT 10
        """).fetchall()

    if not tasks:
        send_message(chat_id, "Pending Task নেই।")
        return

    for task in tasks:
        keyboard = make_keyboard([[
            {
                "text": "✅ Approve",
                "callback_data": f"approve:{task['id']}"
            },
            {
                "text": "❌ Reject",
                "callback_data": f"reject:{task['id']}"
            }
        ]])

        send_message(
            chat_id,
            f"Task #{task['id']}: {task['title']}\n"
            f"Reward: {task['reward']} BDT (TEST ONLY)\n"
            f"Slots: {task['slots']}",
            keyboard
        )


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
        user = message.get("from", {})
        user_id = user.get("id")
        chat_id = message.get("chat", {}).get("id")
        text = (message.get("text") or "").strip()

        if not user_id or not chat_id:
            return jsonify({"ok": True})

        if text == "/start":
            keyboard = make_keyboard([
                [{"text": "👷 Worker", "callback_data": "role:worker"}],
                [{"text": "💼 Client", "callback_data": "role:client"}]
            ])
            send_message(
                chat_id,
                "🦊 Welcome to BMTaskHub!\nতুমি কোন অ্যাকাউন্ট তৈরি করতে চাও?",
                keyboard
            )

        elif text == "/menu":
            main_menu(chat_id, user_id)

        elif text == "/admin":
            admin_panel(chat_id, user_id)

        elif text == "/cancel":
            clear_state(user_id)
            send_message(chat_id, "চলমান কাজ বাতিল করা হয়েছে।")
            main_menu(chat_id, user_id)

        else:
            state, data = get_state(user_id)

            if state in ("title", "description", "reward", "slots"):
                if get_role(user_id) == "client":
                    create_task_step(
                        chat_id, user_id, text, state, data
                    )
                else:
                    clear_state(user_id)
                    send_message(chat_id, "Client অ্যাকাউন্ট প্রয়োজন।")

            elif state == "proof":
                if not text or text.startswith("/"):
                    send_message(
                        chat_id,
                        "Proof হিসেবে লেখা বা লিংক পাঠাও। বাতিল করতে /cancel লেখো।"
                    )
                else:
                    task_id = data.get("task_id")

                    with connect_db() as con:
                        cur = con.execute("""
                        UPDATE submissions
                        SET proof=?, status='pending'
                        WHERE task_id=? AND worker_id=?
                        AND status='working'
                        """, (text[:2000], task_id, user_id))

                    clear_state(user_id)

                    if cur.rowcount:
                        send_message(
                            chat_id,
                            "✅ Proof জমা হয়েছে। Admin যাচাই করবে।"
                        )
                    else:
                        send_message(
                            chat_id,
                            "Submission পাওয়া যায়নি। /menu দিয়ে আবার চেষ্টা করো।"
                        )

                    main_menu(chat_id, user_id)

            else:
                send_message(chat_id, "মেনু দেখতে /menu লেখো।")

    callback = update.get("callback_query")

    if callback:
        user = callback.get("from", {})
        user_id = user.get("id")
        chat_id = callback.get("message", {}).get("chat", {}).get("id")
        query_id = callback.get("id")
        action = callback.get("data", "")

        try:
            telegram_api("answerCallbackQuery", {
                "callback_query_id": query_id
            })
        except Exception:
            pass

        if not user_id or not chat_id:
            return jsonify({"ok": True})

        if action.startswith("role:"):
            role = action.split(":", 1)[1]

            if role in ("worker", "client"):
                register_user(user, role)
                clear_state(user_id)
                send_message(chat_id, "✅ Account তৈরি হয়েছে।")
                main_menu(chat_id, user_id)

        elif action == "post":
            if get_role(user_id) != "client":
                send_message(chat_id, "এই ফিচারের জন্য Client অ্যাকাউন্ট প্রয়োজন।")
            else:
                set_state(user_id, "title", {})
                send_message(
                    chat_id,
                    "Task-এর শিরোনাম লেখো। বাতিল করতে /cancel লেখো।"
                )

        elif action == "mytasks" and get_role(user_id) == "client":
            with connect_db() as con:
                tasks = con.execute("""
                SELECT id, title, status, reward
                FROM tasks
                WHERE client_id=?
                ORDER BY id DESC LIMIT 10
                """, (user_id,)).fetchall()

            if not tasks:
                send_message(chat_id, "তোমার কোনো Task নেই।")
            else:
                for task in tasks:
                    send_message(
                        chat_id,
                        f"#{task['id']} {task['title']}\n"
                        f"Status: {task['status']}\n"
                        f"Reward: {task['reward']} BDT (TEST ONLY)"
                    )

        elif action == "browse" and get_role(user_id) == "worker":
            browse_tasks(chat_id)

        elif action == "balance" and get_role(user_id) == "worker":
            with connect_db() as con:
                row = con.execute(
                    "SELECT amount FROM balances WHERE telegram_id=?",
                    (user_id,)
                ).fetchone()

            amount = row["amount"] if row else 0
            send_message(
                chat_id,
                f"💰 Test balance: {amount:.2f} BDT\nএটি আসল টাকা নয়।"
            )

        elif action == "mysub" and get_role(user_id) == "worker":
            with connect_db() as con:
                rows = con.execute("""
                SELECT s.task_id, s.status, t.title
                FROM submissions s
                JOIN tasks t ON t.id=s.task_id
                WHERE s.worker_id=?
                ORDER BY s.id DESC LIMIT 10
                """, (user_id,)).fetchall()

            if not rows:
                send_message(chat_id, "এখনো কোনো submission নেই।")
            else:
                for row in rows:
                    send_message(
                        chat_id,
                        f"Task #{row['task_id']} {row['title']}\n"
                        f"Status: {row['status']}"
                    )

        elif action.startswith("claim:") and get_role(user_id) == "worker":
            try:
                task_id = int(action.split(":", 1)[1])

                with connect_db() as con:
                    con.execute("BEGIN IMMEDIATE")

                    task = con.execute("""
                    SELECT id FROM tasks
                    WHERE id=? AND status='approved' AND slots > 0
                    """, (task_id,)).fetchone()

                    if not task:
                        send_message(chat_id, "Task আর পাওয়া যাচ্ছে না।")
                    else:
                        con.execute("""
                        INSERT INTO submissions
                        (task_id, worker_id, proof, status)
                        VALUES (?, ?, '', 'working')
                        """, (task_id, user_id))

                        cur = con.execute("""
                        UPDATE tasks SET slots=slots-1
                        WHERE id=? AND slots>0 AND status='approved'
                        """, (task_id,))

                        if cur.rowcount != 1:
                            raise ValueError("No slots available")

                        set_state(user_id, "proof", {"task_id": task_id})
                        send_message(
                            chat_id,
                            "কাজটি সম্পন্ন করে Proof হিসেবে লেখা বা লিংক পাঠাও।\n"
                            "বাতিল করতে /cancel লেখো।"
                        )

            except sqlite3.IntegrityError:
                send_message(chat_id, "তুমি এই Task আগে নিয়েছ।")
            except (ValueError, TypeError):
                send_message(chat_id, "Task পাওয়া যাচ্ছে না বা আর কোনো Slot নেই।")

        elif action.startswith("approve:") or action.startswith("reject:"):
            if not ADMIN_ID or user_id != ADMIN_ID:
                send_message(chat_id, "⛔ Admin access নেই।")
            else:
                decision, raw_id = action.split(":", 1)

                try:
                    task_id = int(raw_id)
                    status = "approved" if decision == "approve" else "rejected"

                    with connect_db() as con:
                        cur = con.execute("""
                        UPDATE tasks SET status=?
                        WHERE id=? AND status='pending'
                        """, (status, task_id))

                    if cur.rowcount:
                        send_message(chat_id, f"Task #{task_id}: {status}")
                    else:
                        send_message(chat_id, "Task পাওয়া যায়নি বা আগেই যাচাই হয়েছে।")

                except (ValueError, TypeError):
                    send_message(chat_id, "Task ID ভুল।")

    return jsonify({"ok": True})


def set_webhook():
    if not TOKEN or not PUBLIC_URL:
        print("BOT_TOKEN or PUBLIC_URL is missing.")
        return

    data = {
        "url": PUBLIC_URL.rstrip("/") + "/telegram-webhook"
    }

    if WEBHOOK_SECRET:
        data["secret_token"] = WEBHOOK_SECRET

    try:
        telegram_api("setWebhook", data)
    except Exception as exc:
        print("Webhook setup failed:", exc)


init_db()
set_webhook()
