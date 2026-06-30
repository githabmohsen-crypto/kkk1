import os
import sqlite3
import time
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ---------------- CONFIG ----------------
TOKEN = os.environ.get("BOT_TOKEN")

ADMIN_IDS = [8815017184]

# ---------------- DATABASE ----------------
conn = sqlite3.connect("tickets.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    message TEXT,
    file_id TEXT,
    type TEXT,
    status TEXT,
    time INTEGER
)
""")
conn.commit()

user_state = {}
reply_map = {}


# ---------------- SAVE TICKET ----------------
def save_ticket(uid, username, msg, file_id, type_):
    cur.execute("""
        INSERT INTO tickets (user_id, username, message, file_id, type, status, time)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (uid, username, msg, file_id, type_, "open", int(time.time())))
    conn.commit()
    return cur.lastrowid


# ---------------- GET OPEN TICKETS ----------------
def get_open_tickets():
    cur.execute("SELECT id, user_id, message FROM tickets WHERE status='open'")
    return cur.fetchall()


# ---------------- CLOSE TICKET ----------------
def close_ticket(ticket_id):
    cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (ticket_id,))
    conn.commit()


# ---------------- MAIN MENU ----------------
def user_menu():
    return ReplyKeyboardMarkup([
        ["📩 ارسال تیکت"],
        ["📜 قوانین", "📞 ارتباط"]
    ], resize_keyboard=True)


def admin_menu():
    return ReplyKeyboardMarkup([
        ["📋 تیکت‌های باز"],
        ["🔄 رفرش"]
    ], resize_keyboard=True)


# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id

    if uid in ADMIN_IDS:
        await update.message.reply_text("🛠 پنل ادمین فعال شد", reply_markup=admin_menu())
        return

    await update.message.reply_text("👋 خوش آمدی", reply_markup=user_menu())


# ---------------- HANDLE ----------------
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.message.from_user
    uid = user.id
    text = update.message.text

    # ---------- USER MENU ----------
    if uid not in ADMIN_IDS:

        if text == "📜 قوانین":
            await update.message.reply_text("📜 قوانین: احترام الزامی است")
            return

        if text == "📞 ارتباط":
            await update.message.reply_text("📞 از طریق تیکت پیام بده")
            return

        if text == "📩 ارسال تیکت":
            user_state[uid] = True
            await update.message.reply_text("✍ پیام خود را ارسال کن:")
            return

        # ---------- TICKET ----------
        if user_state.get(uid):

            msg_type = "text"
            content = text
            file_id = None

            if update.message.photo:
                msg_type = "photo"
                file_id = update.message.photo[-1].file_id
                content = "📷 عکس"

            elif update.message.document:
                msg_type = "file"
                file_id = update.message.document.file_id
                content = "📎 فایل"

            elif update.message.voice:
                msg_type = "voice"
                file_id = update.message.voice.file_id
                content = "🎤 ویس"

            ticket_id = save_ticket(uid, user.username, content, file_id, msg_type)

            for admin in ADMIN_IDS:
                msg = await context.bot.send_message(
                    chat_id=admin,
                    text=f"""
🎫 Ticket #{ticket_id}

👤 @{user.username}
🆔 {uid}

📝 {content}
"""
                )

                reply_map[msg.message_id] = uid

            await update.message.reply_text(f"✅ ثبت شد #{ticket_id}")
            user_state[uid] = False
            return

    # ---------- ADMIN PANEL ----------
    if uid in ADMIN_IDS:

        if text == "📋 تیکت‌های باز":

            tickets = get_open_tickets()

            if not tickets:
                await update.message.reply_text("✅ تیکتی وجود ندارد")
                return

            for t in tickets:
                ticket_id, user_id, msg = t

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{user_id}")],
                    [InlineKeyboardButton("✔ بستن", callback_data=f"close_{ticket_id}")]
                ])

                await update.message.reply_text(
                    f"🎫 Ticket #{ticket_id}\n👤 {user_id}\n📝 {msg}",
                    reply_markup=keyboard
                )

        if text == "🔄 رفرش":
            await update.message.reply_text("🔄 رفرش شد", reply_markup=admin_menu())


# ---------------- CALLBACK ----------------
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    data = query.data

    # ---------- CLOSE TICKET ----------
    if data.startswith("close_"):
        ticket_id = int(data.split("_")[1])
        close_ticket(ticket_id)
        await query.edit_message_text("✔ تیکت بسته شد")

    # ---------- REPLY MODE ----------
    if data.startswith("reply_"):
        user_id = int(data.split("_")[1])
        reply_map[query.message.message_id] = user_id
        await query.edit_message_text("✉ پیام را ارسال کن")


# ---------------- ADMIN REPLY ----------------
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):

    uid = update.effective_user.id
    text = update.message.text

    if uid in ADMIN_IDS and update.message.reply_to_message:

        msg_id = update.message.reply_to_message.message_id

        if msg_id in reply_map:

            target = reply_map[msg_id]

            await context.bot.send_message(
                chat_id=target,
                text=f"📩 پاسخ پشتیبانی:\n\n{text}"
            )

            await update.message.reply_text("✅ ارسال شد")


# ---------------- RUN ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(MessageHandler(filters.TEXT, admin_reply))

app.run_polling()
