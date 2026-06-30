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
    filters
)

# ---------------- CONFIG ----------------
TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL = "@Kaletek_news"
ADMIN_IDS = [8815017184]

# ---------------- DB ----------------
db = sqlite3.connect("kaletek.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
user_id INTEGER PRIMARY KEY,
username TEXT,
first_name TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS tickets(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
username TEXT,
message TEXT,
message_type TEXT,
file_id TEXT,
status TEXT,
rating INTEGER,
created INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS banned(
user_id INTEGER PRIMARY KEY
)
""")

db.commit()

# ---------------- STATE ----------------
ticket_mode = {}
broadcast_mode = {}
reply_state = {}

# ---------------- SAVE USER ----------------
def save_user(user):
    cur.execute("""
    INSERT OR IGNORE INTO users(user_id, username, first_name)
    VALUES (?, ?, ?)
    """, (user.id, user.username or "", user.first_name or ""))
    db.commit()

# ---------------- BAN CHECK ----------------
def is_banned(uid):
    cur.execute("SELECT 1 FROM banned WHERE user_id=?", (uid,))
    return cur.fetchone() is not None

# ---------------- MEMBER CHECK ----------------
async def is_member(context, user_id):
    try:
        m = await context.bot.get_chat_member(CHANNEL, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

# ---------------- ENFORCE ----------------
async def enforce_channel(update, context):
    uid = update.effective_user.id
    save_user(update.effective_user)

    if is_banned(uid):
        await update.message.reply_text("🚫 شما از سیستم مسدود شده‌اید")
        return False

    if not await is_member(context, uid):
        await update.message.reply_text(
            "🚨 برای استفاده از ربات باید عضو کانال باشید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 عضویت", url=f"https://t.me/{CHANNEL.replace('@','')}")],
                [InlineKeyboardButton("🔄 بررسی عضویت", callback_data="check")]
            ])
        )
        return False

    return True

# ---------------- MENUS ----------------
def user_menu():
    return ReplyKeyboardMarkup(
        [["📞 تماس با پشتیبانی"], ["📜 قوانین"], ["👤 پروفایل"]],
        resize_keyboard=True
    )

def admin_menu():
    return ReplyKeyboardMarkup(
        [["📋 تیکت‌های باز"], ["📊 گزارش پنل"], ["📣 ارسال همگانی"], ["🚫 مدیریت بن"]],
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
    data = q.data

    save_user(q.from_user)

    if is_banned(uid):
        await q.message.reply_text("🚫 شما بن هستید")
        return

    if data == "check":
        if await is_member(context, uid):
            await context.bot.send_message(uid, "✅ عضویت تایید شد", reply_markup=user_menu())
        return

    if data == "start_ticket":
        ticket_mode[uid] = True
        await q.message.reply_text("✍ پیام خود را ارسال کنید")
        return

    if data.startswith("reply_"):
        reply_state[uid] = int(data.split("_")[1])
        await q.message.reply_text("✉ پاسخ را بنویس")
        return

    if data.startswith("ban_"):
        target = int(data.split("_")[1])
        cur.execute("INSERT OR IGNORE INTO banned(user_id) VALUES(?)", (target,))
        db.commit()
        await q.message.reply_text("🚫 بن شد")
        try:
            await context.bot.send_message(target, "🚫 شما بن شدید")
        except:
            pass
        return

    if data.startswith("close_"):
        tid = int(data.split("_")[1])

        cur.execute("SELECT user_id FROM tickets WHERE id=?", (tid,))
        row = cur.fetchone()
        if not row:
            return

        user_id = row[0]

        cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
        db.commit()

        await q.edit_message_text("✔ بسته شد")

        await context.bot.send_message(
            user_id,
            "🙏 تیکت شما بسته شد\n\n⭐ لطفاً میزان رضایت خود را ثبت کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ عالی", callback_data=f"rate_{tid}_5")],
                [InlineKeyboardButton("🙂 خوب", callback_data=f"rate_{tid}_4")],
                [InlineKeyboardButton("😐 متوسط", callback_data=f"rate_{tid}_3")],
                [InlineKeyboardButton("😠 ضعیف", callback_data=f"rate_{tid}_1")]
            ])
        )
        return

    if data.startswith("rate_"):
        _, tid, score = data.split("_")
        cur.execute("UPDATE tickets SET rating=? WHERE id=?", (int(score), tid))
        db.commit()
        await q.message.edit_text("🙏 ممنون از ثبت نظر شما 💙")
        return

# ---------------- HANDLE ----------------
async def handle(update: Update, context):
    if not await enforce_channel(update, context):
        return

    uid = update.effective_user.id
    save_user(update.effective_user)

    text = update.message.text
    photo = update.message.photo
    document = update.message.document

    # ---------------- ADMIN REPLY (TEXT/PHOTO/DOC FIX) ----------------
    if uid in ADMIN_IDS and uid in reply_state:
        target = reply_state[uid]

        if photo:
            await context.bot.send_photo(target, photo[-1].file_id, caption="📩 پاسخ پشتیبانی")

        elif document:
            await context.bot.send_document(target, document.file_id, caption="📩 پاسخ پشتیبانی")

        else:
            await context.bot.send_message(target, f"📩 پاسخ پشتیبانی:\n\n{text}")

        await update.message.reply_text("✅ ارسال شد")
        del reply_state[uid]
        return

    # ---------------- PROFILE ----------------
    if text == "👤 پروفایل":
        cur.execute("SELECT COUNT(*) FROM tickets WHERE user_id=?", (uid,))
        ticket_count = cur.fetchone()[0]

        cur.execute("SELECT AVG(rating) FROM tickets WHERE user_id=? AND rating IS NOT NULL", (uid,))
        avg = cur.fetchone()[0] or 0

        cur.execute("SELECT status FROM tickets WHERE user_id=? ORDER BY id DESC LIMIT 1", (uid,))
        last = cur.fetchone()
        last_status = last[0] if last else "ندارد"

        await update.message.reply_text(
            f"👤 پروفایل شما\n\n"
            f"🆔 ID: {uid}\n"
            f"🎫 تعداد تیکت‌ها: {ticket_count}\n"
            f"⭐ میانگین رضایت: {round(avg,2)}\n"
            f"📌 آخرین وضعیت: {last_status}"
        )
        return

    # ---------------- ADMIN PANEL ----------------
    if uid in ADMIN_IDS:

        if text == "📊 گزارش پنل":
            cur.execute("SELECT COUNT(*) FROM users")
            users = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM tickets")
            tickets = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM banned")
            banned_count = cur.fetchone()[0]

            cur.execute("SELECT AVG(rating) FROM tickets WHERE rating IS NOT NULL")
            avg = cur.fetchone()[0] or 0

            await update.message.reply_text(
                f"📊 گزارش سیستم\n\n"
                f"👤 کاربران: {users}\n"
                f"🎫 تیکت‌ها: {tickets}\n"
                f"🚫 بن: {banned_count}\n"
                f"⭐ میانگین رضایت: {round(avg,2)}"
            )
            return

        if text == "📋 تیکت‌های باز":
            cur.execute("""
            SELECT id, user_id, username, message, message_type, file_id
            FROM tickets
            WHERE status='open'
            ORDER BY id DESC
            """)

            rows = cur.fetchall()

            if not rows:
                await update.message.reply_text("📭 تیکتی نیست")
                return

            for tid, user, username, msg, mtype, file_id in rows:

                base = f"""🎫 تیکت #{tid}

👤 کاربر: {username}
🆔 ID: {user}

📝 پیام:
{msg}
"""

                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{user}")],
                    [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")],
                    [InlineKeyboardButton("🚫 بن", callback_data=f"ban_{user}")]
                ])

                if mtype == "photo":
                    await update.message.reply_photo(file_id, caption=base, reply_markup=kb)

                elif mtype == "document":
                    await update.message.reply_document(file_id, caption=base, reply_markup=kb)

                else:
                    await update.message.reply_text(base, reply_markup=kb)

            return

        if text == "📣 ارسال همگانی":
            broadcast_mode[uid] = True
            await update.message.reply_text("✍ پیام همگانی را ارسال کنید:")
            return

    # ---------------- BROADCAST ----------------
    if broadcast_mode.get(uid):
        cur.execute("SELECT user_id FROM users")
        for u in cur.fetchall():
            try:
                await context.bot.send_message(u[0], text)
            except:
                pass

        broadcast_mode[uid] = False
        await update.message.reply_text("✅ ارسال شد")
        return

    # ---------------- TICKET ----------------
    if ticket_mode.get(uid):

        username = update.effective_user.username or "ندارد"

        if photo:
            file_id = photo[-1].file_id
            msg_type = "photo"
            msg_text = ""

        elif document:
            file_id = document.file_id
            msg_type = "document"
            msg_text = ""

        else:
            file_id = None
            msg_type = "text"
            msg_text = text

        cur.execute("""
        INSERT INTO tickets(user_id, username, message, message_type, file_id, status, rating, created)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (uid, username, msg_text, msg_type, file_id, "open", None, int(time.time())))

        db.commit()
        ticket_id = cur.lastrowid

        for admin in ADMIN_IDS:
            await context.bot.send_message(
                admin,
                f"🎫 تیکت جدید #{ticket_id}\n\n👤 @{username}\n🆔 {uid}\n\n📝 {text}"
            )

        ticket_mode[uid] = False
        await update.message.reply_text("✅ تیکت ثبت شد")
        return

# ---------------- RUN ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(callback))
app.add_handler(MessageHandler(filters.ALL, handle))

app.run_polling()
