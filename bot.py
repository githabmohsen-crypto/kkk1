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
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set!")

CHANNEL = "@Kaletek_news"
ADMIN_IDS = [8815017184]

# ---------------- DB ----------------
db = sqlite3.connect("kaletek.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
user_id INTEGER PRIMARY KEY
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS tickets(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
username TEXT,
message TEXT,
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

cur.execute("""
CREATE TABLE IF NOT EXISTS profiles(
user_id INTEGER PRIMARY KEY,
username TEXT,
join_time INTEGER,
tickets_count INTEGER DEFAULT 0
)
""")

db.commit()

# ---------------- STATES ----------------
ticket_mode = {}
reply_mode = {}
broadcast_mode = {}

# ---------------- BAN CHECK ----------------
def is_banned(uid):
    cur.execute("SELECT 1 FROM banned WHERE user_id=?", (uid,))
    return cur.fetchone() is not None

# ---------------- MEMBERSHIP ----------------
async def is_member(context, user_id):
    try:
        m = await context.bot.get_chat_member(CHANNEL, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False

# ---------------- ENFORCE ----------------
async def enforce_channel(update, context):

    uid = update.effective_user.id

    cur.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))
    db.commit()

    # create profile
    cur.execute("""
    INSERT OR IGNORE INTO profiles(user_id, username, join_time, tickets_count)
    VALUES (?, ?, ?, 0)
    """, (
        uid,
        update.effective_user.username or "ندارد",
        int(time.time())
    ))
    db.commit()

    if is_banned(uid):
        await update.message.reply_text("🚫 شما از سیستم مسدود شده‌اید")
        return False

    if not await is_member(context, uid):
        await update.message.reply_text(
            "🚨 برای استفاده از ربات باید عضو کانال باشید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 عضویت", url="https://t.me/Kaletek_news")],
                [InlineKeyboardButton("🔄 بررسی عضویت", callback_data="check")]
            ])
        )
        return False

    return True

# ---------------- MENUS ----------------
def user_menu():
    return ReplyKeyboardMarkup(
        [["👤 پروفایل من"], ["📞 تماس با پشتیبانی"], ["📜 قوانین"]],
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

    # reply start
    if q.data.startswith("reply_"):
        target = int(q.data.split("_")[1])
        reply_mode[uid] = target
        await q.message.reply_text("✉ پاسخ را بنویس")
        return

    # close ticket
    if q.data.startswith("close_"):

        tid = int(q.data.split("_")[1])

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

    # rating
    if q.data.startswith("rate_"):
        _, tid, score = q.data.split("_")

        cur.execute("UPDATE tickets SET rating=? WHERE id=?", (int(score), tid))
        db.commit()

        await q.message.edit_text("🙏 ممنون از ثبت نظر شما 💙")
        return

    # ban
    if q.data.startswith("ban_"):
        target = int(q.data.split("_")[1])
        cur.execute("INSERT OR IGNORE INTO banned(user_id) VALUES(?)", (target,))
        db.commit()
        await q.edit_message_text("🚫 کاربر بن شد")
        return

# ---------------- HANDLE ----------------
async def handle(update: Update, context):

    if not await enforce_channel(update, context):
        return

    uid = update.effective_user.id
    text = update.message.text

    # ---------------- ADMIN ----------------
    if uid in ADMIN_IDS:

        if text == "🚫 مدیریت بن":
            await update.message.reply_text("✍ /ban id | /unban id")
            return

        if text.startswith("/ban"):
            target = int(text.split()[1])
            cur.execute("INSERT OR IGNORE INTO banned(user_id) VALUES(?)", (target,))
            db.commit()
            await update.message.reply_text("🚫 بن شد")
            return

        if text.startswith("/unban"):
            target = int(text.split()[1])
            cur.execute("DELETE FROM banned WHERE user_id=?", (target,))
            db.commit()
            await update.message.reply_text("✅ آنبن شد")
            return

        if text == "📊 گزارش پنل":

            cur.execute("SELECT COUNT(*) FROM users")
            users = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM tickets")
            tickets = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM banned")
            banned = cur.fetchone()[0]

            cur.execute("SELECT AVG(rating) FROM tickets WHERE rating IS NOT NULL")
            avg = cur.fetchone()[0] or 0

            cur.execute("SELECT user_id FROM banned")
            banned_list = cur.fetchall()
            banned_text = "\n".join([str(x[0]) for x in banned_list]) or "ندارد"

            await update.message.reply_text(
                f"📊 گزارش سیستم\n\n"
                f"👤 کاربران: {users}\n"
                f"🎫 تیکت‌ها: {tickets}\n"
                f"🚫 بن: {banned}\n"
                f"⭐ میانگین رضایت: {round(avg,2)}\n\n"
                f"🚫 لیست بن‌ها:\n{banned_text}"
            )
            return

        if text == "📣 ارسال همگانی":
            broadcast_mode[uid] = True
            await update.message.reply_text("✍ متن یا عکس ارسال کنید")
            return

        if broadcast_mode.get(uid):

            cur.execute("SELECT user_id FROM users")
            users = [r[0] for r in cur.fetchall()]

            photo = update.message.photo
            caption = update.message.caption or text or ""

            for u in users:
                try:
                    if photo:
                        await context.bot.send_photo(u, photo[-1].file_id, caption=caption)
                    else:
                        await context.bot.send_message(u, f"📢 {caption}")
                except:
                    pass

            broadcast_mode[uid] = False
            await update.message.reply_text("✅ ارسال شد")
            return

        if uid in reply_mode:

            target = reply_mode[uid]

            await context.bot.send_message(
                target,
                f"📩 پاسخ پشتیبانی:\n\n{text}"
            )

            await update.message.reply_text("✅ ارسال شد")
            del reply_mode[uid]
            return

    # ---------------- USER ----------------
    if uid not in ADMIN_IDS:

        if text == "👤 پروفایل من":
            cur.execute("SELECT username, join_time, tickets_count FROM profiles WHERE user_id=?", (uid,))
            row = cur.fetchone()

            if row:
                username, join_time, tickets = row

                await update.message.reply_text(
                    f"👤 پروفایل شما\n\n"
                    f"🆔 ID: {uid}\n"
                    f"👤 Username: @{username}\n"
                    f"🎫 تیکت‌ها: {tickets}\n"
                    f"📅 عضویت: {time.strftime('%Y-%m-%d', time.localtime(join_time))}"
                )
            return

        if text == "📜 قوانین":
            await update.message.reply_text(
                "📜 قوانین سیستم پشتیبانی\n\n"
                "1️⃣ احترام\n2️⃣ اسپم ممنوع\n3️⃣ توضیح کامل\n4️⃣ اطلاعات حساس نفرستید"
            )
            return

        if text == "📞 تماس با پشتیبانی":
            await update.message.reply_text(
                "✍ پیام خود را ارسال کنید:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✍ شروع", callback_data="start_ticket")]
                ])
            )
            return

        if text:

            ticket_mode[uid] = True

            username = update.effective_user.username or "ندارد"

            cur.execute("""
            INSERT INTO tickets(user_id, username, message, status, created)
            VALUES (?, ?, ?, ?, ?)
            """, (uid, username, text, "open", int(time.time())))
            db.commit()

            tid = cur.lastrowid

            cur.execute("""
            UPDATE profiles SET tickets_count = tickets_count + 1 WHERE user_id=?
            """, (uid,))
            db.commit()

            for admin in ADMIN_IDS:
                await context.bot.send_message(
                    admin,
                    f"🎫 تیکت #{tid}\n👤 @{username}\n🆔 {uid}\n\n📝 {text}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{uid}")],
                        [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")],
                        [InlineKeyboardButton("🚫 بن کاربر", callback_data=f"ban_{uid}")]
                    ])
                )

            await update.message.reply_text("✅ تیکت ثبت شد")
            ticket_mode[uid] = False
            return

# ---------------- RUN ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(callback))
app.add_handler(MessageHandler(filters.ALL, handle))

app.run_polling()
