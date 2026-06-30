import os
import sqlite3
import time
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
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
CHANNEL = "@Kaletek_news"
ADMIN_IDS = [8815017184]

# ---------------- DB ----------------
conn = sqlite3.connect("tickets.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    message TEXT,
    status TEXT,
    time INTEGER
)
""")
conn.commit()

ticket_to_user = {}
user_state = {}

# ---------------- CHECK CHANNEL ----------------
async def is_member(context, user_id):
    try:
        member = await context.bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ---------------- MENUS ----------------
def user_menu():
    return ReplyKeyboardMarkup(
        [["📩 ارسال تیکت"], ["📜 قوانین", "📞 ارتباط"]],
        resize_keyboard=True
    )

def admin_menu():
    return ReplyKeyboardMarkup(
        [["📋 تیکت‌های باز"]],
        resize_keyboard=True
    )

# ---------------- START ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if not await is_member(context, uid):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/Kaletek_news")],
            [InlineKeyboardButton("✅ عضو شدم", callback_data="check")]
        ])

        await update.message.reply_text(
            "🚀 برای استفاده باید عضو کانال باشی:",
            reply_markup=keyboard
        )
        return

    if uid in ADMIN_IDS:
        await update.message.reply_text("🛠 پنل ادمین", reply_markup=admin_menu())
    else:
        await update.message.reply_text("👋 خوش آمدی", reply_markup=user_menu())

# ---------------- CALLBACK (JOIN CHECK) ----------------
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    if query.data == "check":
        if await is_member(context, uid):
            await query.message.reply_text("✅ تایید شد")
            await context.bot.send_message(uid, "👋 وارد شدی", reply_markup=user_menu())
        else:
            await query.message.reply_text("❌ هنوز عضو نشدی")

# ---------------- DB FUNCTIONS ----------------
def save_ticket(uid, username, msg):
    cur.execute("""
        INSERT INTO tickets (user_id, username, message, status, time)
        VALUES (?, ?, ?, 'open', ?)
    """, (uid, username, msg, int(time.time())))
    conn.commit()
    return cur.lastrowid

def get_tickets():
    cur.execute("SELECT id, user_id, message FROM tickets WHERE status='open'")
    return cur.fetchall()

def close_ticket(tid):
    cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
    conn.commit()

# ---------------- MAIN HANDLER ----------------
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid = user.id
    text = update.message.text

    # ---------------- USER ----------------
    if uid not in ADMIN_IDS:

        if text == "📜 قوانین":
            await update.message.reply_text("📜 احترام الزامی است")
            return

        if text == "📞 ارتباط":
            await update.message.reply_text("📞 از تیکت استفاده کن")
            return

        if text == "📩 ارسال تیکت":
            user_state[uid] = True
            await update.message.reply_text("✍ پیام خود را بفرست")
            return

        if user_state.get(uid):
            tid = save_ticket(uid, user.username, text)

            for admin in ADMIN_IDS:
                msg = await context.bot.send_message(
                    admin,
                    f"🎫 Ticket #{tid}\n👤 @{user.username}\n🆔 {uid}\n\n📝 {text}"
                )

                ticket_to_user[msg.message_id] = uid

            await update.message.reply_text(f"✅ ثبت شد #{tid}")
            user_state[uid] = False
            return

    # ---------------- ADMIN ----------------
    if uid in ADMIN_IDS:

        if text == "📋 تیکت‌های باز":
            tickets = get_tickets()

            if not tickets:
                await update.message.reply_text("📭 تیکتی نیست")
                return

            for tid, user_id, msg in tickets:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")]
                ])

                await update.message.reply_text(
                    f"🎫 #{tid}\n👤 {user_id}\n📝 {msg}",
                    reply_markup=keyboard
                )

# ---------------- CALLBACK BUTTONS ----------------
async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("close_"):
        tid = int(data.split("_")[1])
        close_ticket(tid)
        await query.edit_message_text("✔ بسته شد")

# ---------------- ADMIN REPLY ----------------
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

    if uid not in ADMIN_IDS:
        return

    if update.message.reply_to_message:
        msg_id = update.message.reply_to_message.message_id

        if msg_id in ticket_to_user:
            target = ticket_to_user[msg_id]

            await context.bot.send_message(
                chat_id=target,
                text=f"📩 پاسخ پشتیبانی:\n\n{text}"
            )

            await update.message.reply_text("✅ ارسال شد")

# ---------------- RUN ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(callback))
app.add_handler(CallbackQueryHandler(buttons))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(MessageHandler(filters.TEXT, admin_reply))

app.run_polling()
