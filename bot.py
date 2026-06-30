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
    filters,
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

user_state = {}
reply_to_user = {}

# ---------------- CHECK CHANNEL MEMBERSHIP ----------------
async def is_member(context, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

# ---------------- KEYBOARDS ----------------
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
        await update.message.reply_text(
            "🚀 برای استفاده باید عضو کانال باشی:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 عضویت", url="https://t.me/Kaletek_news")],
                [InlineKeyboardButton("✅ عضو شدم", callback_data="check")]
            ])
        )
        return

    if uid in ADMIN_IDS:
        await update.message.reply_text("🛠 پنل ادمین", reply_markup=admin_menu())
    else:
        await update.message.reply_text("👋 خوش آمدی", reply_markup=user_menu())

# ---------------- CALLBACK ----------------
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    # membership check
    if query.data == "check":
        if await is_member(context, uid):
            await query.message.reply_text("✅ تایید شد")
            await context.bot.send_message(uid, "👋 وارد شدی", reply_markup=user_menu())
        else:
            await query.message.reply_text("❌ هنوز عضو نشدی")

    # admin reply setup
    elif query.data.startswith("reply_"):
        target = int(query.data.split("_")[1])
        reply_to_user[uid] = target
        await query.message.reply_text("✉ حالا پیام پاسخ را بنویس:")

    # close ticket
    elif query.data.startswith("close_"):
        tid = int(query.data.split("_")[1])
        cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
        conn.commit()
        await query.edit_message_text("✔ تیکت بسته شد")

# ---------------- MESSAGE HANDLER ----------------
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
            await update.message.reply_text("📞 از سیستم تیکت استفاده کنید")
            return

        if text == "📩 ارسال تیکت":
            user_state[uid] = True
            await update.message.reply_text("✍ پیام خود را ارسال کنید:")
            return

        if user_state.get(uid):
            cur.execute("""
                INSERT INTO tickets (user_id, username, message, status, time)
                VALUES (?, ?, ?, 'open', ?)
            """, (uid, user.username, text, int(time.time())))
            conn.commit()

            user_state[uid] = False
            await update.message.reply_text("✅ تیکت ثبت شد")
            return

    # ---------------- ADMIN ----------------
    if uid in ADMIN_IDS:

        if text == "📋 تیکت‌های باز":
            cur.execute("SELECT id, user_id, message FROM tickets WHERE status='open'")
            tickets = cur.fetchall()

            if not tickets:
                await update.message.reply_text("📭 تیکتی نیست")
                return

            for tid, user_id, msg in tickets:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{user_id}")],
                    [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")]
                ])

                await update.message.reply_text(
                    f"🎫 #{tid}\n👤 {user_id}\n📝 {msg}",
                    reply_markup=keyboard
                )

# ---------------- ADMIN REPLY ----------------
async def admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if uid in ADMIN_IDS and uid in reply_to_user:
        target = reply_to_user[uid]

        await context.bot.send_message(
            chat_id=target,
            text=f"📩 پاسخ پشتیبانی:\n\n{update.message.text}"
        )

        await update.message.reply_text("✅ ارسال شد")
        del reply_to_user[uid]

# ---------------- APP ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(callback))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reply))

app.run_polling()
