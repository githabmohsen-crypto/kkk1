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

if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set!")

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

# تیکت فعال (برای چت واقعی)
cur.execute("""
CREATE TABLE IF NOT EXISTS active_tickets(
    user_id INTEGER PRIMARY KEY,
    ticket_id INTEGER
)
""")

db.commit()

# ---------------- STATES ----------------
ticket_mode = {}
reply_mode = {}
broadcast_mode = {}
unban_mode = {}

# ---------------- BAN ----------------
def is_banned(uid):
    cur.execute(
        "SELECT 1 FROM banned WHERE user_id=?",
        (uid,)
    )
    return cur.fetchone() is not None


# ---------------- MEMBER ----------------
async def is_member(context, user_id):
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


# ---------------- ENFORCE ----------------
async def enforce_channel(update, context):

    uid = update.effective_user.id

    cur.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (uid,)
    )

    cur.execute("""
    INSERT OR IGNORE INTO profiles(
        user_id,
        username,
        join_time,
        tickets_count
    )
    VALUES (?, ?, ?, 0)
    """,
    (
        uid,
        update.effective_user.username or "ندارد",
        int(time.time())
    ))

    db.commit()

    if is_banned(uid):

        await update.message.reply_text(
            "🚫 شما از سیستم مسدود شده‌اید"
        )

        return False

    if not await is_member(context, uid):

        await update.message.reply_text(
            "🚨 برای استفاده از ربات باید عضو کانال باشید:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "📢 عضویت",
                        url="https://t.me/Kaletek_news"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔄 بررسی عضویت",
                        callback_data="check"
                    )
                ]
            ])
        )

        return False

    return True


# ---------------- MENUS ----------------
def user_menu():

    return ReplyKeyboardMarkup(
        [
            ["👤 پروفایل من"],
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

        await update.message.reply_text(
            "🛠 پنل ادمین",
            reply_markup=admin_menu()
        )

    else:
        await update.message.reply_text(
            "👋 خوش آمدید",
            reply_markup=user_menu()
        )
        # ---------------- CALLBACK ----------------
async def callback(update: Update, context):

    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    # عضویت
    if q.data == "check":

        if await is_member(context, uid):

            await context.bot.send_message(
                uid,
                "✅ عضویت تایید شد",
                reply_markup=(
                    admin_menu()
                    if uid in ADMIN_IDS
                    else user_menu()
                )
            )

        else:

            await context.bot.send_message(
                uid,
                "❌ هنوز عضو کانال نیستید!",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "📢 عضویت",
                            url="https://t.me/Kaletek_news"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔄 بررسی مجدد",
                            callback_data="check"
                        )
                    ]
                ])
            )

        return

    # شروع تیکت
    if q.data == "start_ticket":

        ticket_mode[uid] = True

        await q.message.reply_text(
            "✍ پیام خود را ارسال کنید"
        )

        return

    # پاسخ ادمین
    if q.data.startswith("reply_"):

        target = int(q.data.split("_")[1])

        reply_mode[uid] = target

        await q.message.reply_text(
            "✉ پاسخ را ارسال کنید"
        )

        return

    # بستن تیکت
    if q.data.startswith("close_"):

        tid = int(q.data.split("_")[1])

        cur.execute(
            "SELECT user_id FROM tickets WHERE id=?",
            (tid,)
        )

        row = cur.fetchone()

        if not row:

            await q.answer("تیکت پیدا نشد")

            return

        user_id = row[0]

        cur.execute(
            "UPDATE tickets SET status='closed' WHERE id=?",
            (tid,)
        )

        cur.execute(
            "DELETE FROM active_tickets WHERE user_id=?",
            (user_id,)
        )

        db.commit()

        await q.edit_message_text(
            "✔ تیکت بسته شد"
        )

        await context.bot.send_message(
            user_id,
            "🙏 تیکت شما بسته شد\n\n⭐ لطفاً میزان رضایت خود را ثبت کنید:",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⭐ عالی",
                        callback_data=f"rate_{tid}_5"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🙂 خوب",
                        callback_data=f"rate_{tid}_4"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "😐 متوسط",
                        callback_data=f"rate_{tid}_3"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "😠 ضعیف",
                        callback_data=f"rate_{tid}_1"
                    )
                ]
            ])
        )

        return

    # امتیاز
    if q.data.startswith("rate_"):

        _, tid, score = q.data.split("_")

        cur.execute(
            "UPDATE tickets SET rating=? WHERE id=?",
            (
                int(score),
                tid
            )
        )

        db.commit()

        await q.edit_message_text(
            "🙏 ممنون از ثبت نظر شما 💙"
        )

        return

    # بن
    if q.data.startswith("ban_"):

        target = int(
            q.data.split("_")[1]
        )

        cur.execute(
            "INSERT OR IGNORE INTO banned(user_id) VALUES(?)",
            (target,)
        )

        db.commit()

        try:

            await context.bot.send_message(
                target,
                "🚫 شما از سیستم مسدود شده‌اید"
            )

        except:
            pass
            await q.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🚫 کاربر بن شد",
                        callback_data="done"
                    )
                ]
            ])
        )

        return
        # ---------------- HANDLE ----------------
async def handle(update: Update, context):

    if not await enforce_channel(update, context):
        return

    uid = update.effective_user.id

    text = update.message.text or ""
    photo = update.message.photo
    caption = update.message.caption or ""

    # ---------------- ADMIN ----------------
    if uid in ADMIN_IDS:

        # ارسال همگانی
        if text == "📣 ارسال همگانی":

            broadcast_mode[uid] = True

            await update.message.reply_text(
                "✍ پیام همگانی را ارسال کنید"
            )

            return


        if broadcast_mode.get(uid):

            cur.execute(
                "SELECT user_id FROM users"
            )

            users = [
                r[0]
                for r in cur.fetchall()
            ]

            count = 0

            for u in users:

                try:

                    if photo:

                        await context.bot.send_photo(
                            u,
                            photo[-1].file_id,
                            caption=caption
                        )

                    else:

                        await context.bot.send_message(
                            u,
                            f"📢 {text}"
                        )

                    count += 1

                except:
                    pass

            broadcast_mode[uid] = False

            await update.message.reply_text(
                f"✅ برای {count} نفر ارسال شد"
            )

            return


        # مدیریت بن
        if text == "🚫 مدیریت بن":

            unban_mode[uid] = True

            await update.message.reply_text(
                "✍ آیدی عددی کاربر را بفرست"
            )

            return


        if unban_mode.get(uid):

            try:

                target = int(text)

                cur.execute(
                    "DELETE FROM banned WHERE user_id=?",
                    (target,)
                )

                db.commit()

                await update.message.reply_text(
                    "✅ رفع بن انجام شد"
                )

            except:

                await update.message.reply_text(
                    "❌ آیدی نامعتبر"
                )

            unban_mode[uid] = False

            return


        # گزارش
        if text == "📊 گزارش پنل":

            cur.execute(
                "SELECT COUNT(*) FROM users"
            )

            users = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM tickets"
            )

            tickets = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*) FROM banned"
            )

            banned = cur.fetchone()[0]

            await update.message.reply_text(

                f"📊 گزارش سیستم\n\n"

                f"👤 کاربران: {users}\n"

                f"🎫 تیکت‌ها: {tickets}\n"

                f"🚫 بن: {banned}"

            )

            return


        # تیکت باز
        if text == "📋 تیکت‌های باز":

            cur.execute("""
            SELECT
            id,
            user_id,
            username,
            message

            FROM tickets

            WHERE status='open'
            """)

            rows = cur.fetchall()

            if not rows:

                await update.message.reply_text(
                    "🎉 تیکت بازی وجود ندارد"
                )

                return

            for tid, user2, username, message in rows:

                keyboard = InlineKeyboardMarkup([

                    [
                        InlineKeyboardButton(
                            "✉ پاسخ",
                            callback_data=f"reply_{user2}"
                        )
                    ],

                    [
                        InlineKeyboardButton(
                            "✔ بستن",
                            callback_data=f"close_{tid}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🚫 بن کاربر",
                            callback_data=f"ban_{user2}"
                        )
                    ]

                ])

                await update.message.reply_text(

                    f"🎫 #{tid}\n"

                    f"👤 @{username}\n"

                    f"📝 {message}",

                    reply_markup=keyboard
                )

            return


        # پاسخ ادمین
        if uid in reply_mode:

            target = reply_mode[uid]

            try:

                if photo:

                    await context.bot.send_photo(
                        target,
                        photo[-1].file_id,
                        caption=caption
                    )

                else:

                    await context.bot.send_message(
                        target,
                        f"📩 پاسخ پشتیبانی:\n\n{text}"
                    )

                await update.message.reply_text(
                    "✅ ارسال شد"
                )

            except:

                await update.message.reply_text(
                    "❌ ارسال نشد"
                )

            del reply_mode[uid]

            return


    # ---------------- USER ----------------

    if text == "👤 پروفایل من":

        cur.execute(
            """
            SELECT
            username,
            join_time,
            tickets_count

            FROM profiles

            WHERE user_id=?
            """,
            (uid,)
        )

        row = cur.fetchone()

        if row:

            await update.message.reply_text(

                f"👤 پروفایل\n\n"

                f"🆔 {uid}\n"

                f"👤 @{row[0]}\n"

                f"🎫 {row[2]}\n"

                f"📅 {time.strftime('%Y-%m-%d', time.localtime(row[1]))}"
            )

        return


    if text == "📜 قوانین":

        await update.message.reply_text(
            "📜 قوانین سیستم پشتیبانی Kaletek"
        )

        return


    if text == "📞 تماس با پشتیبانی":

        ticket_mode[uid] = True

        await update.message.reply_text(

            "برای شروع پیام ارسال کنید",

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


    # چت واقعی تیکت
    if ticket_mode.get(uid):

        username = (
            update.effective_user.username
            or "ندارد"
        )

        cur.execute(
            "SELECT ticket_id FROM active_tickets WHERE user_id=?",
            (uid,)
        )

        row = cur.fetchone()

        if row:

            tid = row[0]

        else:

            cur.execute("""
            INSERT INTO tickets(
            user_id,
            username,
            message,
            status,
            created
            )

            VALUES(?,?,?,?,?)
            """, (
                uid,
                username,
                "",
                "open",
                int(time.time())
            ))

            tid = cur.lastrowid

            cur.execute(
                """
                INSERT OR REPLACE INTO active_tickets
                VALUES(?,?)
                """,
                (uid, tid)
            )

            db.commit()

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
                ],
                [
                    InlineKeyboardButton(
                        "🚫 بن کاربر",
                        callback_data=f"ban_{uid}"
                    )
                ]

            ])

            if photo:

                await context.bot.send_photo(
                    admin,
                    photo[-1].file_id,
                    caption=caption,
                    reply_markup=keyboard
                )

            else:

                await context.bot.send_message(
                    admin,
                    text,
                    reply_markup=keyboard
                )

        await update.message.reply_text(

            "تیکت شما ثبت شد ✅\n\n"

            "درخواست شما در صف بررسی قرار گرفت.\n\n"

            "💙 از همراهی شما سپاسگزاریم."

        )

        return
        # ---------------- UNBAN CMD ----------------
async def unban_cmd(update: Update, context):

    uid = update.effective_user.id

    if uid not in ADMIN_IDS:

        await update.message.reply_text(
            "⛔ دسترسی ندارید"
        )

        return


    if not context.args:

        await update.message.reply_text(
            "❌ مثال:\n/unban 123456789"
        )

        return


    try:

        target = int(
            context.args[0]
        )

    except:

        await update.message.reply_text(
            "❌ آیدی نامعتبر"
        )

        return


    cur.execute(
        "DELETE FROM banned WHERE user_id=?",
        (target,)
    )

    db.commit()

    await update.message.reply_text(
        f"✅ کاربر {target} رفع بن شد"
    )


# ---------------- RUN ----------------
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
    CommandHandler(
        "unban",
        unban_cmd
    )
)

app.add_handler(
    CallbackQueryHandler(
        callback
    )
)

app.add_handler(
    MessageHandler(
        filters.ALL,
        handle
    )
)


print("BOT STARTED")


app.run_polling(
    drop_pending_updates=True
)
