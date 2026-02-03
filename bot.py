import os
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters
)

# ================== الإعدادات (من Render Environment Variables) ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
SUPER_ADMIN = int(os.getenv("SUPER_ADMIN"))

# ================== قاعدة البيانات ==================
conn = sqlite3.connect("bot.db")
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    used_link INTEGER DEFAULT 0
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
)
""")

# إضافة السوبر أدمن تلقائياً
c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (SUPER_ADMIN,))
conn.commit()
conn.close()

# ================== دوال مساعدة ==================

def is_admin(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM admins WHERE user_id=?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r is not None

def user_used(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT used_link FROM users WHERE user_id=?", (user_id,))
    r = c.fetchone()
    conn.close()
    return r and r[0] == 1

def mark_used(user_id):
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("UPDATE users SET used_link=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE used_link=1")
    used = c.fetchone()[0]
    conn.close()
    return total, used

# ================== أوامر المستخدم ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    conn = sqlite3.connect("bot.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "✨━━━━━━━━━━━━━━━✨\n"
        "👋 أهلاً بك في بوابة الانضمام الرسمية\n\n"
        "⚠️ تنبيه هام جداً:\n"
        "• يمنح الرابط مرة واحدة فقط\n"
        "• صالح لمدة 30 دقيقة\n"
        "• يتوقف فور دخولك\n\n"
        "🔑 للحصول على روابط الانضمام:\n"
        "/link\n"
        "✨━━━━━━━━━━━━━━━✨"
    )

async def link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_used(user_id):
        await update.message.reply_text("❌ لقد حصلت على رابط سابقًا.")
        return

    expire_time = datetime.now() + timedelta(minutes=30)

    group_invite = await context.bot.create_chat_invite_link(
        chat_id=GROUP_ID,
        expire_date=expire_time,
        member_limit=1
    )

    channel_invite = await context.bot.create_chat_invite_link(
        chat_id=CHANNEL_ID,
        expire_date=expire_time,
        member_limit=1
    )

    mark_used(user_id)

    await update.message.reply_text(
        f"✨━━━━━━━━━━━━━━━✨\n"
        f"🔗 روابطك الخاصة:\n\n"
        f"👥 القروب:\n{group_invite.invite_link}\n\n"
        f"📢 القناة:\n{channel_invite.invite_link}\n\n"
        f"⏳ صالحة 30 دقيقة\n"
        f"👤 لشخص واحد فقط\n"
        f"⚠️ لا تشارك الروابط\n"
        f"✨━━━━━━━━━━━━━━━✨"
    )

# ================== لوحة الأدمن ==================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("📢 إرسال رسالة", callback_data="broadcast")],
        [InlineKeyboardButton("➕ إضافة أدمن", callback_data="add_admin")]
    ]

    await update.message.reply_text(
        "👑 لوحة التحكم",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin(query.from_user.id):
        return

    if query.data == "stats":
        total, used = get_stats()
        await query.message.reply_text(
            f"📊 الإحصائيات:\n\n"
            f"👤 عدد المستخدمين: {total}\n"
            f"🔗 أخذوا رابط: {used}"
        )

    if query.data == "broadcast":
        context.user_data["broadcast"] = True
        await query.message.reply_text("✍️ أرسل الرسالة الآن.")

    if query.data == "add_admin":
        context.user_data["adding_admin"] = True
        await query.message.reply_text(
            "✍️ أرسل ID أو @username للأدمن الجديد."
        )

# ================== استقبال الإدخال ==================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not is_admin(user_id):
        return

    # إضافة أدمن
    if context.user_data.get("adding_admin"):

        new_admin_id = None

        if text.isdigit():
            new_admin_id = int(text)

        elif text.startswith("@"):
            username = text.replace("@", "")
            try:
                member = await context.bot.get_chat_member(GROUP_ID, username)
                new_admin_id = member.user.id
            except:
                await update.message.reply_text(
                    "❌ لم يتم العثور عليه.\n"
                    "تأكد أنه داخل القروب."
                )
                return
        else:
            await update.message.reply_text(
                "❌ أرسل ID أو @username فقط."
            )
            return

        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_admin_id,))
        conn.commit()
        conn.close()

        context.user_data["adding_admin"] = False

        await update.message.reply_text(
            f"✅ تم إضافة الأدمن:\nID: {new_admin_id}"
        )
        return

    # بث جماعي
    if context.user_data.get("broadcast"):
        conn = sqlite3.connect("bot.db")
        c = conn.cursor()
        c.execute("SELECT user_id FROM users")
        users = c.fetchall()
        conn.close()

        sent = 0
        for user in users:
            try:
                await context.bot.send_message(chat_id=user[0], text=text)
                sent += 1
            except:
                pass

        context.user_data["broadcast"] = False

        await update.message.reply_text(
            f"✅ تم الإرسال إلى {sent} مستخدم."
        )

# ================== التشغيل ==================

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("link", link))
app.add_handler(CommandHandler("admin", admin_panel))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

app.run_polling()