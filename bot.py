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
db.commit()

ticket_mode = {}
reply_mode = {}


# ---------------- CHECK MEMBER ----------------
async def is_member(context, user_id):
    try:
        m = await context.bot.get_chat_member(CHANNEL, user_id)
        return m.status in ["member", "administrator", "creator"]
    except:
        return False


# ---------------- FORCE CHECK ----------------
async def enforce_channel(update, context):

    uid = update.effective_user.id

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
async def callback(update, context):

    q = update.callback_query
    await q.answer()

    uid = q.from_user.id

    # -------- CHECK --------
    if q.data == "check":

        if await is_member(context, uid):

            await context.bot.send_message(
                uid,
                "✅ عضویت تایید شد",
                reply_markup=user_menu()
            )

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


    # -------- START TICKET --------
    if q.data == "start_ticket":

        ticket_mode[uid] = True
        await q.message.reply_text("✍ پیام خود را ارسال کنید")
        return


    # -------- REPLY --------
    if q.data.startswith("reply_"):

        target = int(q.data.split("_")[1])
        reply_mode[uid] = target

        await q.message.reply_text("✉ پاسخ را بنویس")
        return


    # -------- CLOSE --------
    if q.data.startswith("close_"):

        tid = int(q.data.split("_")[1])

        cur.execute("UPDATE tickets SET status='closed' WHERE id=?", (tid,))
        db.commit()

        await q.edit_message_text("✔ بسته شد")
        return


# ---------------- HANDLE ----------------
async def handle(update, context):

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


    # -------- USER --------
    if uid not in ADMIN_IDS:


        # ================= RULES (بدون تغییر متن) =================
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


        # ================= CONTACT (بدون تغییر متن) =================
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


        # ================= TICKET MODE (FIX + MEDIA + USER INFO) =================
        if ticket_mode.get(uid):

            message_type = "text"
            file_id = None
            caption = text

            if update.message.photo:
                message_type = "photo"
                file_id = update.message.photo[-1].file_id

            elif update.message.video:
                message_type = "video"
                file_id = update.message.video.file_id

            elif update.message.document:
                message_type = "document"
                file_id = update.message.document.file_id


            username = update.effective_user.username or "ندارد"
            first_name = update.effective_user.first_name or ""
            last_name = update.effective_user.last_name or ""

            full_name = (first_name + " " + last_name).strip()


            cur.execute("""
            INSERT INTO tickets(user_id, username, message, status, created)
            VALUES (?, ?, ?, ?, ?)
            """, (
                uid,
                username,
                caption,
                "open",
                int(time.time())
            ))

            db.commit()

            tid = cur.lastrowid

            for admin in ADMIN_IDS:

                caption_text = (
                    f"🎫 تیکت #{tid}\n\n"
                    f"👤 نام: {full_name}\n"
                    f"🆔 آیدی: {uid}\n"
                    f"📛 یوزرنیم: @{username if username != 'ندارد' else 'ندارد'}\n\n"
                    f"📝 پیام:\n{caption}"
                )

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{uid}")],
                    [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")]
                ])

                if message_type == "photo":
                    await context.bot.send_photo(admin, file_id, caption=caption_text, reply_markup=keyboard)

                elif message_type == "video":
                    await context.bot.send_video(admin, file_id, caption=caption_text, reply_markup=keyboard)

                elif message_type == "document":
                    await context.bot.send_document(admin, file_id, caption=caption_text, reply_markup=keyboard)

                else:
                    await context.bot.send_message(admin, caption_text, reply_markup=keyboard)

            await update.message.reply_text("✅ تیکت ثبت شد")
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


# ---------------- RUN ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(callback))
app.add_handler(MessageHandler(filters.ALL, handle))

app.run_polling()
