```python
import os
import time
import sqlite3

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN")

CHANNEL = "@Kaletek_news"
ADMIN_IDS = [8815017184]

# ================= DATABASE =================

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

# ================= MEMORY =================

ticket_mode = {}
reply_mode = {}

# ================= UTILITIES =================

async def is_member(context, user_id):
    try:
        member = await context.bot.get_chat_member(
            CHANNEL,
            user_id
        )

        return member.status in (
            "member",
            "administrator",
            "creator"
        )

    except Exception:
        return False


def get_user_menu():
    return ReplyKeyboardMarkup(
        [
            ["📩 ارسال تیکت"],
            ["📜 قوانین", "📞 ارتباط"],
        ],
        resize_keyboard=True
    )


def get_admin_menu():
    return ReplyKeyboardMarkup(
        [
            ["📋 تیکت‌های باز"]
        ],
        resize_keyboard=True
    )

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id

    if not await is_member(context, user_id):

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
                    callback_data="verify"
                )
            ]
        ])

        await update.message.reply_text(
            "برای استفاده ابتدا عضو کانال شوید.",
            reply_markup=keyboard
        )

        return

    if user_id in ADMIN_IDS:

        text = "🛠 پنل مدیریت"
        menu = get_admin_menu()

    else:

        text = "👋 خوش آمدید"
        menu = get_user_menu()

    await update.message.reply_text(
        text,
        reply_markup=menu
    )

# ================= CALLBACK =================

async def callback(update: Update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if query.data == "verify":

        if await is_member(context, user_id):

            await context.bot.send_message(
                chat_id=user_id,
                text="✅ عضویت تایید شد",
                reply_markup=get_user_menu()
            )

        else:

            await query.message.reply_text(
                "❌ هنوز عضو کانال نیستید"
            )

        return

    if query.data.startswith("reply_"):

        target = int(
            query.data.split("_")[1]
        )

        reply_mode[user_id] = target

        await query.message.reply_text(
            "✍ متن پاسخ را ارسال کنید"
        )

        return

    if query.data.startswith("close_"):

        ticket_id = int(
            query.data.split("_")[1]
        )

        cur.execute(
            """
            UPDATE tickets
            SET status='closed'
            WHERE id=?
            """,
            (ticket_id,)
        )

        db.commit()

        await query.edit_message_text(
            "✔ تیکت بسته شد"
        )

# ================= HANDLE MESSAGE =================

async def handle(update: Update, context):

    user_id = update.effective_user.id
    username = update.effective_user.username
    text = update.message.text

    # ---------- ADMIN REPLY ----------

    if user_id in ADMIN_IDS and user_id in reply_mode:

        target = reply_mode.pop(user_id)

        await context.bot.send_message(
            target,
            f"📩 پاسخ پشتیبانی:\n\n{text}"
        )

        await update.message.reply_text(
            "✅ پاسخ ارسال شد"
        )

        return

    # ---------- USER ----------

    if user_id not in ADMIN_IDS:

        if text == "📜 قوانین":

            await update.message.reply_text(
                "احترام و رعایت قوانین الزامی است."
            )

            return

        if text == "📞 ارتباط":

            await update.message.reply_text(
                "برای ارتباط از بخش تیکت استفاده کنید."
            )

            return

        if text == "📩 ارسال تیکت":

            ticket_mode[user_id] = True

            await update.message.reply_text(
                "پیام خود را ارسال کنید."
            )

            return

        if ticket_mode.get(user_id):

            cur.execute("""
            INSERT INTO tickets
            (
                user_id,
                username,
                message,
                status,
                created
            )
            VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                username,
                text,
                "open",
                int(time.time())
            ))

            db.commit()

            ticket_id = cur.lastrowid

            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "✉ پاسخ",
                        callback_data=f"reply_{user_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "✔ بستن",
                        callback_data=f"close_{ticket_id}"
                    )
                ]
            ])

            for admin in ADMIN_IDS:

                await context.bot.send_message(
                    admin,
                    (
                        f"🎫 تیکت #{ticket_id}\n\n"
                        f"👤 {user_id}\n"
                        f"📝 {text}"
                    ),
                    reply_markup=keyboard
                )

            ticket_mode[user_id] = False

            await update.message.reply_text(
                "✅ تیکت ثبت شد"
            )

            return

    # ---------- ADMIN PANEL ----------

    if user_id in ADMIN_IDS:

        if text == "📋 تیکت‌های باز":

            cur.execute("""
            SELECT id, user_id, message
            FROM tickets
            WHERE status='open'
            """)

            rows = cur.fetchall()

            if not rows:

                await update.message.reply_text(
                    "تیکت بازی وجود ندارد."
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
                    (
                        f"🎫 #{tid}\n"
                        f"👤 {user}\n"
                        f"📝 {msg}"
                    ),
                    reply_markup=keyboard
                )

# ================= RUN =================

def main():

    app = (
        Application
        .builder()
        .token(TOKEN)
        .build()
    )

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


if __name__ == "__main__":
    main()
```
