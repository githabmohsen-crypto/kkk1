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
CREATE TABLE IF NOT EXISTS tickets(
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
        m = await context.bot.get_chat_member(CHANNEL, user_id)

        return m.status in ["member", "administrator", "creator"]

    except:
        return False


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
            ["📋 تیکت‌های باز"]
        ],
        resize_keyboard=True
    )


# ---------------- START ----------------
async def start(update: Update, context):

    uid = update.effective_user.id

    if not await is_member(context, uid):

        await update.message.reply_text(
            "🚀 برای استفاده از ربات باید عضو کانال باشید",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "📢 عضویت در کانال",
                        url="https://t.me/Kaletek_news"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "✅ عضو شدم",
                        callback_data="check"
                    )
                ]
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
            "👋 خوش آمدید به Kaletek Support",
            reply_markup=user_menu()
        )


# ---------------- CALLBACK ----------------
async def callback(update: Update, context):

    q = update.callback_query

    await q.answer()

    uid = q.from_user.id


    # ---------- CHECK MEMBER ----------
    if q.data == "check":

        if await is_member(context, uid):

            await context.bot.send_message(
                uid,
                "✅ عضویت تایید شد",
                reply_markup=user_menu()
            )

        else:

            await q.message.reply_text("❌ هنوز عضو کانال نیستی")

        return


    # ---------- START TICKET ----------
    if q.data == "start_ticket":

        ticket_mode[uid] = True

        await q.message.reply_text(
            "✍ لطفاً پیام خود را واضح و کامل ارسال کنید"
        )

        return


    # ---------- REPLY ----------
    if q.data.startswith("reply_"):

        target = int(q.data.split("_")[1])

        reply_mode[uid] = target

        await q.message.reply_text("✉ پاسخ خود را بنویس")

        return


    # ---------- CLOSE ----------
    if q.data.startswith("close_"):

        tid = int(q.data.split("_")[1])

        cur.execute(
            "UPDATE tickets SET status='closed' WHERE id=?",
            (tid,)
        )

        db.commit()

        await q.edit_message_text("✔ تیکت بسته شد")

        return


# ---------------- HANDLE ----------------
async def handle(update: Update, context):

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


    # ---------------- USER ----------------
    if uid not in ADMIN_IDS:

        # قوانین
        if text == "📜 قوانین":

            await update.message.reply_text(
                "📜 قوانین Kaletek\n\n"
                "1️⃣ احترام الزامی است\n"
                "2️⃣ هر تیکت یک موضوع باشد\n"
                "3️⃣ ارسال اسپم ممنوع است\n"
                "4️⃣ اطلاعات کامل بنویسید\n"
                "5️⃣ ارتباط مستقیم با ادمین ممنوع\n"
                "6️⃣ پاسخ ممکن است زمان‌بر باشد\n"
                "7️⃣ اطلاعات حساس ارسال نکنید\n\n"
                "━━━━━━━━━━━━\n"
                "💙 با ارسال پیام قوانین را پذیرفته‌اید"
            )

            return


        # تماس با پشتیبانی
        if text == "📞 تماس با پشتیبانی":

            await update.message.reply_text(
                "✔️ برای دریافت پاسخ از کارشناسان پشتیبانی، از دکمه پایین استفاده کنید.\n\n"
                "‼️ لطفاً موضوع را در قالب یک پیام منسجم و واضح بنویسید؛ "
                "این کار باعث می‌شود پاسخگویی سریع‌تر انجام شود 💙\n\n"
                "✅ با لمس دکمه زیر، گفتگو با تیم پشتیبانی آغاز می‌شود.",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "✍ شروع گفتگو با پشتیبانی",
                            callback_data="start_ticket"
                        )
                    ]
                ])
            )

            return


        # ---------------- TICKET MODE ----------------
        if ticket_mode.get(uid):

            content = text

            if update.message.photo:
                content = "📷 عکس"

            elif update.message.video:
                content = "🎥 ویدیو"

            elif update.message.document:
                content = "📎 فایل"

            cur.execute("""
            INSERT INTO tickets
            (user_id, username, message, status, created)
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

                caption = f"""
🎫 تیکت #{tid}
👤 {uid}

📝 {content}
"""

                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "✉ پاسخ",
                            callback_data=f"reply_{uid}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "✔ بستن",
                            callback_data=f"close_{tid}"
                        )
                    ]
                ])

                await context.bot.send_message(
                    admin,
                    caption,
                    reply_markup=keyboard
                )

            await update.message.reply_text(
                f"✅ تیکت #{tid} ثبت شد"
            )

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
                    [
                        InlineKeyboardButton(
                            "✉ پاسخ",
                            callback_data=f"reply_{user}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "✔ بستن",
                            callback_data=f"close_{tid}"
                        )
                    ]
                ])

                await update.message.reply_text(
                    f"🎫 #{tid}\n👤 {user}\n📝 {msg}",
                    reply_markup=keyboard
                )


# ---------------- RUN ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(callback))
app.add_handler(MessageHandler(filters.ALL, handle))

app.run_polling()
