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
unban_mode = {}

# ---------------- BAN ----------------
def is_banned(uid):
    cur.execute("SELECT 1 FROM banned WHERE user_id=?", (uid,))
    return cur.fetchone() is not None

# ---------------- MEMBER ----------------
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

    cur.execute("""
    INSERT OR IGNORE INTO profiles(user_id, username, join_time, tickets_count)
    VALUES (?, ?, ?, 0)
    """, (uid, update.effective_user.username or "ندارد", int(time.time())))
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

    if q.data == "start_ticket":
        ticket_mode[uid] = True
        await q.message.reply_text("✍ پیام خود را ارسال کنید")
        return

    if q.data.startswith("reply_"):
        reply_mode[uid] = int(q.data.split("_")[1])
        await q.message.reply_text("✉ پاسخ را بنویس")
        return

    if q.data.startswith("close_"):
    
        tid = int(q.data.split("_")[1])
    
        cur.execute(
            "UPDATE tickets SET status='closed' WHERE id=?",
            (tid,)
        )
        
        db.commit()
        
        cur.execute(
            "DELETE FROM active_tickets WHERE user_id=?",
            (user_id,)
        )
        
        db.commit()
        
        await q.edit_message_text("✔ بسته شد")
    
        row = cur.fetchone()
    
        if not row:
            await q.answer("تیکت پیدا نشد")
            return
    
        user_id = row[0]
    
        cur.execute(
            "UPDATE tickets SET status='closed' WHERE id=?",
            (tid,)
        )
    
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

    if q.data.startswith("rate_"):
        _, tid, score = q.data.split("_")
        cur.execute("UPDATE tickets SET rating=? WHERE id=?", (int(score), tid))
        db.commit()
        await q.message.edit_text("🙏 ممنون از ثبت نظر شما 💙")
        return

    if q.data.startswith("ban_"):
    
        target = int(q.data.split("_")[1])
    
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
                [InlineKeyboardButton("🚫 کاربر بن شد", callback_data="done")]
            ])
        )
    
        await q.answer("کاربر بن شد")
    
        return

# ---------------- HANDLE ----------------
async def handle(update: Update, context):

    if not await enforce_channel(update, context):
        return

    uid = update.effective_user.id

    text = update.message.text
    photo = update.message.photo
    caption = update.message.caption or ""

    # ---------------- ADMIN ----------------
    if uid in ADMIN_IDS:

        if text == "📣 ارسال همگانی":
            broadcast_mode[uid] = True
            await update.message.reply_text("✍ پیام همگانی را ارسال کنید")
            return
        if text == "🚫 مدیریت بن":
            unban_mode[uid] = True
            await update.message.reply_text("✍ آیدی عددی کاربر را ارسال کنید")
            return
            if not rows:
                await update.message.reply_text("لیست بن خالی است")
                return
        
            banned_list = "\n".join([str(r[0]) for r in rows])
        
            await update.message.reply_text(
                f"🚫 کاربران بن شده:\n\n{banned_list}"
            )
            return
            if q.data.startswith("unban_"):
                target = int(q.data.split("_")[1])
            
                cur.execute("DELETE FROM banned WHERE user_id=?", (target,))
                db.commit()
            
                await q.answer("رفع بن شد")
                await q.edit_message_text("✅ کاربر از بن خارج شد")
                return

        # FIX 1: REPORT ALWAYS WORKS
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

        if text == "📋 تیکت‌های باز":

            cur.execute("SELECT id, user_id, username, message FROM tickets WHERE status='open'")
            rows = cur.fetchall()

            if not rows:
                await update.message.reply_text("🎉 هیچ تیکت بازی وجود ندارد")
                return

            for tid, uid2, username, message in rows:

                await update.message.reply_text(
                    f"🎫 تیکت #{tid}\n👤 @{username}\n🆔 {uid2}\n\n📝 {message}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✉ پاسخ", callback_data=f"reply_{uid2}")],
                        [InlineKeyboardButton("✔ بستن", callback_data=f"close_{tid}")],
                        [InlineKeyboardButton("🚫 بن کاربر", callback_data=f"ban_{uid2}")]
                    ])
                )
            return


        # ---------------- FIX 2: MEDIA NOT NONE ----------------
        if broadcast_mode.get(uid):
        
            cur.execute("SELECT DISTINCT user_id FROM users")
            users = [r[0] for r in cur.fetchall()]
        
            for u in users:
                try:
                    if photo:
                        await context.bot.send_photo(
                            u,
                            photo[-1].file_id,
                            caption=caption or ""
                        )
                    else:
                        await context.bot.send_message(
                            u,
                            f"📢 {text or caption}"
                        )
                except:
                    pass
        
            broadcast_mode[uid] = False
            await update.message.reply_text("✅ ارسال شد")
            return

        if uid in reply_mode:

            target = reply_mode[uid]

            if photo:
                await context.bot.send_photo(target, photo[-1].file_id, caption=caption or "")
            else:
                await context.bot.send_message(target, f"📩 پاسخ پشتیبانی:\n\n{text}")

            await update.message.reply_text("✅ ارسال شد")
            del reply_mode[uid]
            return
        if uid in ADMIN_IDS and unban_mode.get(uid):
    
            target = int(text)
        
            cur.execute("DELETE FROM banned WHERE user_id=?", (target,))
            db.commit()
        
            await update.message.reply_text(f"✅ کاربر {target} رفع بن شد")
        
            unban_mode[uid] = False
            return

    # ---------------- USER ----------------
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
            "‼️ لطفاً موضوع را در قالب یک پیام منسجم و واضح بنویسید؛ این کار باعث می‌شود پاسخگویی سریع‌تر انجام شود 💙\n\n"
            "✅ با لمس دکمه زیر، گفتگو با تیم پشتیبانی آغاز می‌شود.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✍ شروع گفتگو با پشتیبانی", callback_data="start_ticket")]
            ])
        )
        return

    if ticket_mode.get(uid):
    
        username = update.effective_user.username or "ندارد"
    
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
    
            cur.execute("""
            INSERT INTO active_tickets(
            user_id,
            ticket_id
            )
            VALUES(?,?)
            """, (
                uid,
                tid
            ))
    
            db.commit()
    
    
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "✔ بستن",
                    callback_data=f"close_{tid}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🚫 بن",
                    callback_data=f"ban_{uid}"
                )
            ]
        ])
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✉️ پاسخ", callback_data=f"reply_{uid}")],
            [InlineKeyboardButton("✔️ بستن", callback_data=f"close_{tid}")],
            [InlineKeyboardButton("🚫 بن کاربر", callback_data=f"ban_{uid}")],
            [InlineKeyboardButton("✅ رفع بن", callback_data=f"unban_{uid}")]
        ])
    
    
        for admin in ADMIN_IDS:
    
            if photo:
    
                await context.bot.send_photo(
                    admin,
                    photo[-1].file_id,
                    caption=f"🎫 #{tid}\n👤 @{username}\n🆔 {uid}\n\n{caption}",
                    reply_markup=keyboard
                )
    
            else:
    
                await context.bot.send_message(
                    admin,
                    f"🎫 #{tid}\n👤 @{username}\n🆔 {uid}\n\n{text}",
                    reply_markup=keyboard
                )
    
    
        await update.message.reply_text(
                "تیکت شما به واحد پشتیبانی ارسال شد ✅\n\n"
        
                "1️⃣ درخواست شما در صف بررسی تیم پشتیبانی قرار گرفت و در اولین فرصت پاسخ داده خواهد شد.\n\n"
                    
                "2️⃣ لطفاً از ارسال پیام‌های تکراری یا اسپم خودداری کنید تا روند رسیدگی سریع‌تر انجام شود.\n\n"
                    
                "3️⃣ زمان پاسخ‌دهی ممکن است بسته به حجم درخواست‌ها متفاوت باشد.\n\n"
                    
                "💙 از صبوری و همراهی شما سپاسگزاریم."
                )
        return
async def unban_cmd(update: Update, context):

    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ دسترسی ندارید")
        return

    if not context.args:
        await update.message.reply_text("❌ مثال: /unban 123456789")
        return

    target = int(context.args[0])

    cur.execute("DELETE FROM banned WHERE user_id=?", (target,))
    db.commit()

    await update.message.reply_text(f"✅ رفع بن شد: {target}")
# ---------------- RUN ----------------
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(callback))
app.add_handler(MessageHandler(filters.ALL, handle))

app.add_handler(CommandHandler("unban", unban_cmd))

app.run_polling()
