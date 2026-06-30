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

# ---------------- DATABASE ----------------
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

# ---------------- CHECK MEMBER ----------------
async def is_member(context, user_id):
    try:
        member = await context.bot.get_chat_member(CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False


# ---------------- MENUS ----------------
def user_menu():
    return ReplyKeyboardMarkup(
        [
            ["📩 ارسال تیکت"],
            ["📜 قوانین", "📞 ارتباط"]
        ],
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
            "🚀 برای استفاده باید عضو کانال باشید",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 عضویت در کانال", url="https://t.me/Kaletek_news")],
                [InlineKeyboardButton("✅ عضو شدم", callback_data="check")]
            ])
        )
        return

    if uid in ADMIN_IDS:
        await update.message.reply_text(
            "🛠 پنل ادمین Kaletek",
            reply_markup=admin_menu()
        )
    else:
        await update.message.reply_text(
            "👋 خوش آمدی به Kaletek Support",
            reply_markup=user_menu()
        )


# ---------------- CALLBACK ----------------
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id

    if query.data == "check":
        if await is_member(context, uid):
            await context.bot.send_message(
                uid,
                "✅ عضویت تایید شد",
                reply_markup=user_menu()
            )
        else:
            await query.message.reply_text("❌ هنوز عضو کانال نیستی")

    elif query.data.startswith("reply_"):
        target = int(query.data.split("_")[1])
        reply_mode[uid] = target
        await query.message.reply_text("✉ پیام پاسخ را ارسال کنید")

    elif query.data.startswith("close_"):
        tid = int(query.data.split("_")[1])

        cur.execute(
            "UPDATE tickets SET status='closed' WHERE id=?",
            (tid,)
        )
        db.commit()

        await query.edit_message_text("✔ تیکت بسته شد")


# ---------------- HANDLE MESSAGES ----------------
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text

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

    # ---------------- USER SECTION ----------------
    if uid not in ADMIN_IDS:

        if text == "📜 قوانین":
            await update.message.reply_text(
                "📜 قوانین سیستم پشتیبانی Kalatek\n\n"
                "1️⃣ احترام الزامی است\n"
                "2️⃣ هر تیکت یک موضوع\n"
                "3️⃣ ارسال اسپم ممنوع\n"
                "4️⃣ توضیح کامل مشکل\n"
                "5️⃣ ارتباط مستقیم با ادمین ممنوع\n"
                "6️⃣ پاسخ‌گویی ممکن است زمان‌بر باشد\n"
                "7️⃣ اطلاعات حساس ارسال نکنید\n\n"
                "━━━━━━━━━━━━\n"
                "✅ ارسال تیکت یعنی پذیرش قوانین"
            )
            return

        if text == "📞 ارتباط":
            await update.message.reply_text(
                "📞 لطفاً از بخش 📩 ارسال تیکت استفاده کنید"
            )
            return

        if text == "📩 ارسال تیکت":
            ticket_mode[uid] = True
            await update.message.reply_text("✍ پیام خود را ارسال کنید")
            return

        if ticket_mode.get(uid):
            content = text

            if update.message.photo:
                content = "📷 عکس"
            elif update.message.video:
                content = "🎥 ویدیو"
            elif update.message.document:
                content = "📎 فایل"

            cur.execute("""
                INSERT INTO tickets (user_id, username, message, status, created)
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
                base_text = f"""
🎫 تیکت #{tid}
👤 {uid}

📝 {content}
"""

                if update.message.photo:
                    await context.bot.send_photo(
                        admin,
                        update.message.photo[-1].file_id,
                        caption=base_text
                    )

                elif update.message.video:
                    await context.bot.send_video(
                        admin,
                        update.message.video.file_id,
                        caption=base_text
                    )

                elif update.message.document:
                    await context.bot.send_document(
                        admin,
                        update.message.document.file_id,
                        caption=base_text
                    )

                else:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{uid}")],
                        [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")]
                    ])

                    await context.bot.send_message(
                        admin,
                        base_text,
                        reply_markup=keyboard
                    )

            await update.message.reply_text(f"✅ تیکت #{tid} ثبت شد")
            ticket_mode[uid] = False
            return

    # ---------------- ADMIN PANEL ----------------
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
