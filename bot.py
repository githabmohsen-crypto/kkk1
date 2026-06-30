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
CHANNEL = "@Kaletek_news"
ADMIN_IDS = [8815017184]

# ---------------- DB ----------------
db = sqlite3.connect("tickets.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    message TEXT,
    status TEXT,
    created INTEGER
)
""")
db.commit()

ticket_mode = {}
reply_mode = {}

# ---------------- CHECK MEMBERSHIP ----------------
async def is_member(context, user_id):
    try:
        member = await context.bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


# ---------------- FORCE CHECK ----------------
async def enforce_channel(update, context):
    uid = update.effective_user.id

    if not await is_member(context, uid):
        await update.message.reply_text(
            "🚨 دسترسی شما غیرفعال شد!\n\n"
            "برای استفاده از ربات باید عضو کانال باشید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/Kaletek_news")],
                [InlineKeyboardButton("🔄 بررسی عضویت", callback_data="check")]
            ])
        )
        return False

    return True


# ---------------- MENUS ----------------
def user_menu():
    return ReplyKeyboardMarkup(
        [["📞 تماس با پشتیبانی"], ["📜 قوانین"]],
        resize_keyboard=True
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        [["📋 تیکت‌های باز"]],
        resize_keyboard=True
    )


# ---------------- START ----------------
async def start(update: Update, context):
    if not await enforce_channel(update, context):
        return

    uid = update.effective_user.id

    if uid in ADMIN_IDS:
        await update.message.reply_text("🛠 پنل ادمین", reply_markup=admin_menu())
    else:
        await update.message.reply_text("👋 خوش آمدید", reply_markup=user_menu())


# ---------------- CALLBACK ----------------
async def callback(update: Update, context):
    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    # CHECK MEMBERSHIP
    if q.data == "check":
        if await is_member(context, uid):
            await context.bot.send_message(uid, "✅ عضویت تایید شد", reply_markup=user_menu())
        else:
            await context.bot.send_message(
                uid,
                "❌ هنوز عضو کانال نیستید!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📢 عضویت", url="https://t.me/Kaletek_news")],
                    [InlineKeyboardButton("🔄 بررسی مجدد", callback_data="check")]
                ])
            )
        return

    # START TICKET
    if q.data == "start_ticket":
        ticket_mode[uid] = True
        await q.message.reply_text("✍ پیام خود را ارسال کنید")
        return

    # REPLY
    if q.data.startswith("reply_"):
        target = int(q.data.split("_")[1])
        reply_mode[uid] = target
        await q.message.reply_text("✉ پاسخ را بنویس")
        return

    # CLOSE TICKET
    if q.data.startswith("close_"):
        tid = int(q.data.split("_")[1])

        cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
        db.commit()

        await q.edit_message_text("✔ بسته شد")
        return


# ---------------- MESSAGE HANDLER ----------------
async def handle(update: Update, context):
    if not await enforce_channel(update, context):
        return

    uid = update.effective_user.id
    text = update.message.text

    # -------- ADMIN REPLY --------
    if uid in ADMIN_IDS and uid in reply_mode:
        target = reply_mode[uid]

        await context.bot.send_message(
            target,
            f"📩 پاسخ پشتیبانی:\n\n{text}"
        )

        await update.message.reply_text("✅ ارسال شد")
        del reply_mode[uid]
        return

    # -------- USER SIDE --------
    if uid not in ADMIN_IDS:

        if text == "📜 قوانین":
            await update.message.reply_text(
                "📜 قوانین Kaletek\n\n"
                "1️⃣ احترام الزامی است\n"
                "2️⃣ اسپم ممنوع\n"
                "3️⃣ اطلاعات دقیق بنویسید\n"
                "4️⃣ ارتباط مستقیم با ادمین ممنوع\n"
                "5️⃣ ارسال اطلاعات حساس ممنوع\n\n"
                "💙 با استفاده از ربات قوانین را پذیرفتید"
            )
            return

        if text == "📞 تماس با پشتیبانی":
            await update.message.reply_text(
                "✔️ برای ارسال تیکت از دکمه زیر استفاده کنید:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✍ شروع گفتگو", callback_data="start_ticket")]
                ])
            )
            return

        # -------- TICKET MODE --------
        if ticket_mode.get(uid):

            content = text

            if update.message.photo:
                content = "📷 عکس"
            elif update.message.video:
                content = "🎥 ویدیو"
            elif update.message.document:
                content = "📎 فایل"

            cur.execute("""
                INSERT INTO tickets(user_id, username, message, status, created)
                VALUES (?, ?, ?, ?, ?)
            """, (
                uid,
                update.effective_user.username,
                content,
                "open",
                int(time.time())
            ))

            db.commit()
            tid = cur.lastrowid

            for admin in ADMIN_IDS:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{uid}")],
                    [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")]
                ])

                await context.bot.send_message(
                    admin,
                    f"🎫 تیکت #{tid}\n👤 {uid}\n\n📝 {content}",
                    reply_markup=keyboard
                )

            await update.message.reply_text(f"✅ تیکت #{tid} ثبت شد")
            ticket_mode[uid] = False
            return

    # -------- ADMIN PANEL --------
    if uid in ADMIN_IDS:

        if text == "📋 تیکت‌های باز":

            cur.execute("""
                SELECT id, user_id, message
                FROM tickets
                WHERE status='open'
            """)

            rows = cur.fetchall()

            if not rows:
                await update.message.reply_text("📭 تیکتی نیست")
                return

            for tid, user, msg in rows:

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{user}")],
                    [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")]
                ])

                await update.message.reply_text(
                    f"🎫 #{tid}\n👤 {user}\n📝 {msg}",
                    reply_markup=keyboard
                )


# ---------------- RUN BOT ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(callback))
app.add_handler(MessageHandler(filters.ALL, handle))

app.run_polling()
