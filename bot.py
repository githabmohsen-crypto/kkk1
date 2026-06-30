import os
import sqlite3
import time

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

TOKEN = os.environ.get("BOT_TOKEN")

CHANNEL = "@Kaletek_news"
ADMIN_IDS = [8815017184]

# ---------------- DATABASE ----------------

db = sqlite3.connect(
    "tickets.db",
    check_same_thread=False
)

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

# ---------------- CHECK MEMBER ----------------

async def check_member(context, user_id):

    try:

        member = await context.bot.get_chat_member(
            CHANNEL,
            user_id
        )

        return member.status in [
            "member",
            "administrator",
            "creator"
        ]

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
        [
            ["📋 تیکت‌های باز"]
        ],
        resize_keyboard=True
    )


# ---------------- START ----------------

async def start(update: Update, context):

    uid = update.effective_user.id

    if not await check_member(context, uid):

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "📢 عضویت",
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

        await update.message.reply_text(
            "برای استفاده عضو کانال شو",
            reply_markup=keyboard
        )

        return

    if uid in ADMIN_IDS:

        await update.message.reply_text(
            "🛠 پنل ادمین",
            reply_markup=admin_menu()
        )

    else:

        await update.message.reply_text(
            "👋 خوش آمدی",
            reply_markup=user_menu()
        )


# ---------------- CALLBACK ----------------

async def callback(update: Update, context):

    query = update.callback_query

    await query.answer()

    uid = query.from_user.id

    if query.data == "check":

        if await check_member(context, uid):

            await context.bot.send_message(
                chat_id=uid,
                text="✅ تایید شد",
                reply_markup=user_menu()
            )

        else:

            await query.message.reply_text(
                "❌ هنوز عضو نیستی"
            )

    elif query.data.startswith("reply_"):

        target = int(
            query.data.split("_")[1]
        )

        reply_mode[uid] = target

        await query.message.reply_text(
            "✍ پاسخ را بنویس"
        )

    elif query.data.startswith("close_"):

        tid = int(
            query.data.split("_")[1]
        )

        cur.execute(
            """
            UPDATE tickets
            SET status='closed'
            WHERE id=?
            """,
            (tid,)
        )

        db.commit()

        await query.edit_message_text(
            "✔ بسته شد"
        )


# ---------------- HANDLE ----------------

async def handle(update: Update, context):

    uid = update.effective_user.id
    text = update.message.text

    # -------- ADMIN REPLY --------

    if uid in ADMIN_IDS and uid in reply_mode:

        target = reply_mode[uid]

        await context.bot.send_message(
            target,
            f"📩 پاسخ پشتیبانی:\n\n{text}"
        )

        await update.message.reply_text(
            "✅ ارسال شد"
        )

        del reply_mode[uid]

        return


    # -------- USER --------

    if uid not in ADMIN_IDS:

        if text == "📜 قوانین":

            await update.message.reply_text(
                "احترام الزامی است"
            )

            return

        if text == "📞 ارتباط":

            await update.message.reply_text(
                "از تیکت استفاده کن"
            )

            return

        if text == "📩 ارسال تیکت":

            ticket_mode[uid] = True

            await update.message.reply_text(
                "پیام را ارسال کن"
            )

            return

        if ticket_mode.get(uid):

            cur.execute(
                """
                INSERT INTO tickets
                (
                    user_id,
                    username,
                    message,
                    status,
                    created
                )

                VALUES
                (?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    update.effective_user.username,
                    text,
                    "open",
                    int(time.time())
                )
            )

            db.commit()

            tid = cur.lastrowid

            for admin in ADMIN_IDS:

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
                    f"""
🎫 تیکت #{tid}

👤 {uid}

📝 {text}
""",
                    reply_markup=keyboard
                )

            await update.message.reply_text(
                "✅ ثبت شد"
            )

            ticket_mode[uid] = False

            return


    # -------- ADMIN --------

    if uid in ADMIN_IDS:

        if text == "📋 تیکت‌های باز":

            cur.execute(
                """
                SELECT
                    id,
                    user_id,
                    message

                FROM tickets

                WHERE status='open'
                """
            )

            rows = cur.fetchall()

            if not rows:

                await update.message.reply_text(
                    "تیکتی نیست"
                )

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
                    f"🎫 {tid}\n👤 {user}\n📝 {msg}",
                    reply_markup=keyboard
                )


# ---------------- RUN ----------------

app = Application.builder()\
    .token(TOKEN)\
    .build()

app.add_handler(
    CommandHandler(
        "start",
        start
    )
)

app.add_handler(
    CallbackQueryHandler(
        callback
    )
)

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle
    )
)

app.run_polling()
