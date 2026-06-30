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

# ---------------- DATABASE ----------------
db = sqlite3.connect("tickets.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS tickets(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
username TEXT,
message TEXT,
status TEXT,
created INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS banned(
user_id INTEGER PRIMARY KEY
)
""")

db.commit()

ticket_mode = {}
reply_mode = {}
broadcast_mode = {}
rating_mode = {}


# ---------------- CHECK BAN ----------------
def is_banned(uid):
    cur.execute("SELECT user_id FROM banned WHERE user_id=?", (uid,))
    return cur.fetchone() is not None


# ---------------- CHECK MEMBER ----------------
async def is_member(context, user_id):
    try:
        m = await context.bot.get_chat_member(CHANNEL, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False


async def enforce_channel(update, context):

    uid = update.effective_user.id

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
        [
            ["📞 تماس با پشتیبانی"],
            ["📜 قوانین"]
        ],
        resize_keyboard=True
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        [
            ["📋 تیکت‌های باز"],
            ["📊 گزارش پنل"],
            ["📣 ارسال همگانی"],
            ["🚫 مدیریت بن"]
        ],
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


    # CLOSE + RATING
    if q.data.startswith("close_"):

        tid = int(q.data.split("_")[1])

        cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
        db.commit()

        await q.edit_message_text("✔ بسته شد")

        await context.bot.send_message(
            uid,
            "🙏 تیکت شما بسته شد\n\n⭐ لطفاً میزان رضایت خود را ثبت کنید:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⭐ عالی", callback_data="rate_5")],
                [InlineKeyboardButton("🙂 خوب", callback_data="rate_4")],
                [InlineKeyboardButton("😐 متوسط", callback_data="rate_3")],
                [InlineKeyboardButton("😠 ضعیف", callback_data="rate_1")]
            ])
        )
        return


    # RATING SAVE
    if q.data.startswith("rate_"):
        rating_mode[uid] = int(q.data.split("_")[1])
        await q.message.edit_text("🙏 ممنون از ثبت نظر شما 💙")
        return


# ---------------- HANDLE ----------------
async def handle(update: Update, context):

    if not await enforce_channel(update, context):
        return

    uid = update.effective_user.id
    text = update.message.text
    username = update.effective_user.username or "ندارد"


    # ---------------- BAN PANEL ----------------
    if uid in ADMIN_IDS:

        if text == "🚫 مدیریت بن":
            await update.message.reply_text("✍ بن: /ban ID | آنبن: /unban ID")
            return

        if text and text.startswith("/ban"):
            target = int(text.split()[1])
            cur.execute("INSERT OR IGNORE INTO banned(user_id) VALUES(?)", (target,))
            db.commit()
            await update.message.reply_text("🚫 کاربر بن شد")
            return

        if text and text.startswith("/unban"):
            target = int(text.split()[1])
            cur.execute("DELETE FROM banned WHERE user_id=?", (target,))
            db.commit()
            await update.message.reply_text("✅ آنبن شد")
            return


    # ---------------- BROADCAST MEDIA ----------------
    if uid in ADMIN_IDS and text == "📣 ارسال همگانی":
        broadcast_mode[uid] = True
        await update.message.reply_text("✍ پیام (متن یا عکس + کپشن) را ارسال کنید")
        return


    if uid in ADMIN_IDS and broadcast_mode.get(uid):

        cur.execute("SELECT user_id FROM tickets")
        users = set([r[0] for r in cur.fetchall()])

        photo = update.message.photo
        caption = text

        for u in users:
            try:
                if photo:
                    await context.bot.send_photo(
                        u,
                        photo[-1].file_id,
                        caption=caption or ""
                    )
                else:
                    await context.bot.send_message(u, f"📢 {caption}")
            except:
                pass

        broadcast_mode[uid] = False
        await update.message.reply_text("✅ ارسال شد")
        return


    # ---------------- ADMIN REPLY ----------------
    if uid in ADMIN_IDS and uid in reply_mode:

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


        if text == "📜 قوانین":
            await update.message.reply_text(
                "📜 قوانین سیستم پشتیبانی Kalatek\n\n"
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
                "‼️ لطفاً موضوع را در قالب یک پیام منسجم و واضح بنویسید؛ این کار باعث می‌شود پاسخگویی سریع‌تر انجام شود 💙\n\n"
                "✅ با لمس دکمه زیر، گفتگو با تیم پشتیبانی آغاز می‌شود.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✍ شروع گفتگو با پشتیبانی", callback_data="start_ticket")]
                ])
            )
            return


        # ---------------- TICKET ----------------
        if ticket_mode.get(uid):

            caption = text

            cur.execute("""
            INSERT INTO tickets(user_id, username, message, status, created)
            VALUES (?, ?, ?, ?, ?)
            """, (uid, username, caption, "open", int(time.time())))

            db.commit()

            tid = cur.lastrowid

            for admin in ADMIN_IDS:

                await context.bot.send_message(
                    admin,
                    f"🎫 تیکت #{tid}\n👤 @{username}\n🆔 {uid}\n\n📝 {caption}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{uid}")],
                        [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")]
                    ])
                )

            await update.message.reply_text("✅ تیکت ثبت شد")
            ticket_mode[uid] = False
            return


    # ---------------- ADMIN PANEL ----------------
    if uid in ADMIN_IDS:

        if text == "📊 گزارش پنل":

            cur.execute("SELECT COUNT(*) FROM tickets")
            total = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM tickets WHERE status='closed'")
            closed = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM banned")
            banned = cur.fetchone()[0]

            await update.message.reply_text(
                f"📊 گزارش سیستم\n\n"
                f"🎫 کل تیکت‌ها: {total}\n"
                f"✔ بسته شده: {closed}\n"
                f"🚫 کاربران بن: {banned}"
            )
            return


        if text == "📋 تیکت‌های باز":

            cur.execute("SELECT id, user_id, message FROM tickets WHERE status='open'")
            rows = cur.fetchall()

            if not rows:
                await update.message.reply_text("📭 تیکتی نیست")
                return

            for tid, user, msg in rows:

                await update.message.reply_text(
                    f"🎫 #{tid}\n👤 {user}\n📝 {msg}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{user}")],
                        [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")]
                    ])
                )


# ---------------- RUN ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(callback))
app.add_handler(MessageHandler(filters.ALL, handle))

app.run_polling()
