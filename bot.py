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

# ---------------- BAN ----------------
def is_banned(uid):
    cur.execute("SELECT 1 FROM banned WHERE user_id=?", (uid,))
    return cur.fetchone() is not None


# ---------------- SAVE USER ----------------
def save_user(user):
    cur.execute("""
    INSERT OR IGNORE INTO users(user_id, username, first_name)
    VALUES (?, ?, ?)
    """, (user.id, user.username or "", user.first_name or ""))
    db.commit()


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
                [InlineKeyboardButton("📢 عضویت", url="https://t.me/Kaletek_news")],
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
    save_user(q.from_user)

    # CHECK CHANNEL
    if q.data == "check":
        if await is_member(context, uid):
            await context.bot.send_message(uid, "✅ عضویت تایید شد", reply_markup=user_menu())
        return


    # START TICKET
    if q.data == "start_ticket":
        ticket_mode[uid] = True
        await q.message.reply_text("✍ پیام خود را ارسال کنید")
        return


    # COPY ID (FIXED)
    if q.data.startswith("copy_"):
        user_id = q.data.split("_")[1]
        await q.answer(text=f"ID: {user_id}", show_alert=True)
        return


    # BAN (FIXED)
    if q.data.startswith("ban_"):
        target = int(q.data.split("_")[1])
        cur.execute("INSERT OR IGNORE INTO banned(user_id) VALUES(?)", (target,))
        db.commit()
        await q.message.reply_text("🚫 بن شد")
        return


    # CLOSE + SEND RATING TO USER (FIXED)
    if q.data.startswith("close_"):

        tid = int(q.data.split("_")[1])

        cur.execute("SELECT user_id FROM tickets WHERE id=?", (tid,))
        user_id = cur.fetchone()[0]

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


    # RATING SAVE
    if q.data.startswith("rate_"):

        _, tid, score = q.data.split("_")

        cur.execute("UPDATE tickets SET rating=? WHERE id=?", (int(score), tid))
        db.commit()

        await q.message.edit_text("🙏 ممنون از ثبت نظر شما 💙")
        return


# ---------------- HANDLE ----------------
async def handle(update: Update, context):

    if not await enforce_channel(update, context):
        return

    uid = update.effective_user.id
    text = update.message.text

    save_user(update.effective_user)


    # ---------------- ADMIN ----------------
    if uid in ADMIN_IDS:


        # BROADCAST
        if text == "📣 ارسال همگانی":
            broadcast_mode[uid] = True
            await update.message.reply_text("✍ متن یا عکس ارسال کنید")
            return


        if broadcast_mode.get(uid):

            cur.execute("SELECT user_id FROM users")
            users = [r[0] for r in cur.fetchall()]

            photo = update.message.photo

            for u in users:
                try:
                    if photo:
                        await context.bot.send_photo(u, photo[-1].file_id, caption=text or "")
                    else:
                        await context.bot.send_message(u, f"📢 {text}")
                except:
                    pass

            broadcast_mode[uid] = False
            await update.message.reply_text("✅ ارسال شد")
            return


        # BAN PANEL
        if text == "🚫 مدیریت بن":
            await update.message.reply_text("/ban id | /unban id")
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


    # ---------------- USER ----------------

    if text == "📜 قوانین":
        await update.message.reply_text(
            "📜 قوانین سیستم پشتیبانی Kaletek\n\n"
            "1️⃣ احترام الزامی است\n"
            "2️⃣ هر تیکت یک موضوع مشخص\n"
            "3️⃣ ارسال اسپم ممنوع\n"
            "4️⃣ توضیحات کامل بنویسید\n"
            "5️⃣ ارتباط مستقیم با ادمین ممنوع\n"
            "6️⃣ زمان پاسخ‌گویی ممکن است متفاوت باشد\n"
            "7️⃣ اطلاعات حساس ارسال نکنید\n\n"
            "━━━━━━━━━━━━\n"
            "💙 با استفاده از ربات قوانین را پذیرفته‌اید"
        )
        return


    if text == "📞 تماس با پشتیبانی":
        await update.message.reply_text(
            "✔️ برای دریافت پاسخ از کارشناسان پشتیبانی، از دکمه پایین استفاده کنید.\n\n"
            "‼️ لطفاً موضوع را در قالب یک پیام منسجم و واضح بنویسید 💙\n\n"
            "✅ با لمس دکمه زیر، گفتگو با تیم پشتیبانی آغاز می‌شود.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✍ شروع گفتگو با پشتیبانی", callback_data="start_ticket")]
            ])
        )
        return


    # ---------------- TICKET ----------------
    if ticket_mode.get(uid):

        username = update.effective_user.username or "ندارد"

        cur.execute("""
        INSERT INTO tickets(user_id, username, message, status, created)
        VALUES (?, ?, ?, ?, ?)
        """, (uid, username, text, "open", int(time.time())))

        db.commit()

        tid = cur.lastrowid

        for admin in ADMIN_IDS:

            await context.bot.send_message(
                admin,
                f"""🎫 تیکت #{tid}

👤 نام: {update.effective_user.first_name}
📛 یوزرنیم: @{username}
🆔 ID: {uid}

📝 پیام:
{text}
""",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 کپی ID", callback_data=f"copy_{uid}")],
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
