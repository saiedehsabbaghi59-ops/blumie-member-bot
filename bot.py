import os
import sqlite3
import threading
from datetime import datetime, date

from flask import Flask
from bale import (
    Bot,
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


# =========================================================
# تنظیمات Render
# =========================================================

app = Flask(__name__)


@app.route("/")
def home():
    return "🌸 Blumie Bot is running!"


@app.route("/health")
def health():
    return "OK"


def run_web_server():
    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )


# =========================================================
# تنظیمات بات
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN تنظیم نشده است!")

if not ADMIN_ID:
    raise ValueError("ADMIN_ID تنظیم نشده است!")


ADMIN_ID = int(ADMIN_ID)

bot = Bot(token=BOT_TOKEN)


# =========================================================
# دیتابیس
# =========================================================

DB_NAME = "blumie.db"


def get_db():
    conn = sqlite3.connect(
        DB_NAME,
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_db()
    cursor = conn.cursor()

    # کاربران
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            coins INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            total_spent INTEGER DEFAULT 0,
            joined_at TEXT,
            last_daily TEXT
        )
    """)

    # کانال‌های عضویت اجباری
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS required_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            title TEXT,
            username TEXT,
            link TEXT
        )
    """)

    # کدهای هدیه
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gift_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            coins INTEGER,
            max_users INTEGER,
            used_users INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    # استفاده از کدهای هدیه
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gift_usages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT,
            user_id INTEGER,
            UNIQUE(code, user_id)
        )
    """)

    # سفارش‌ها
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            members INTEGER,
            coins INTEGER,
            status TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# حالت‌های موقت ادمین
# =========================================================

admin_states = {}


# =========================================================
# ابزارهای دیتابیس کاربران
# =========================================================

def save_user(user):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user.user_id,)
    )

    exists = cursor.fetchone()

    if not exists:

        cursor.execute("""
            INSERT INTO users (
                user_id,
                first_name,
                username,
                coins,
                total_earned,
                total_spent,
                joined_at
            )
            VALUES (?, ?, ?, 0, 0, 0, ?)
        """, (
            user.user_id,
            user.first_name or "",
            user.username or "",
            datetime.now().isoformat()
        ))

    else:

        cursor.execute("""
            UPDATE users
            SET first_name = ?,
                username = ?
            WHERE user_id = ?
        """, (
            user.first_name or "",
            user.username or "",
            user.user_id
        ))

    conn.commit()
    conn.close()


def get_user(user_id):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )

    user = cursor.fetchone()

    conn.close()

    return user


def add_coins(user_id, amount):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET coins = coins + ?,
            total_earned = total_earned + ?
        WHERE user_id = ?
    """, (
        amount,
        amount,
        user_id
    ))

    conn.commit()
    conn.close()


def remove_coins(user_id, amount):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users
        SET coins = coins - ?,
            total_spent = total_spent + ?
        WHERE user_id = ?
          AND coins >= ?
    """, (
        amount,
        amount,
        user_id,
        amount
    ))

    success = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return success


# =========================================================
# پنل اصلی کاربر
# =========================================================

def user_panel():

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            text="🪙 سکه‌های من",
            callback_data="user_coins"
        ),
        row=1
    )

    keyboard.add(
        InlineKeyboardButton(
            text="🎁 جمع‌آوری سکه",
            callback_data="collect_coins"
        ),
        row=2
    )

    keyboard.add(
        InlineKeyboardButton(
            text="👥 سفارش ممبر",
            callback_data="member_order"
        ),
        row=3
    )

    keyboard.add(
        InlineKeyboardButton(
            text="💰 خرید سکه",
            callback_data="buy_coins"
        ),
        row=4
    )

    keyboard.add(
        InlineKeyboardButton(
            text="🎟️ کد هدیه",
            callback_data="gift_code"
        ),
        row=5
    )

    keyboard.add(
        InlineKeyboardButton(
            text="👤 حساب من",
            callback_data="my_account"
        ),
        row=6
    )

    keyboard.add(
        InlineKeyboardButton(
            text="📊 فعالیت من",
            callback_data="my_activity"
        ),
        row=7
    )

    keyboard.add(
        InlineKeyboardButton(
            text="📞 پشتیبانی",
            callback_data="support"
        ),
        row=8
    )

    return keyboard


# =========================================================
# پنل مدیریت
# =========================================================

def admin_panel():

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            text="📢 مدیریت عضویت اجباری",
            callback_data="admin_channels"
        ),
        row=1
    )

    keyboard.add(
        InlineKeyboardButton(
            text="🪙 مدیریت سکه",
            callback_data="admin_coins"
        ),
        row=2
    )

    keyboard.add(
        InlineKeyboardButton(
            text="🎁 مدیریت کدهای هدیه",
            callback_data="admin_gifts"
        ),
        row=3
    )

    keyboard.add(
        InlineKeyboardButton(
            text="👥 مدیریت سفارش‌ها",
            callback_data="admin_orders"
        ),
        row=4
    )

    keyboard.add(
        InlineKeyboardButton(
            text="👤 کاربران",
            callback_data="admin_users"
        ),
        row=5
    )

    keyboard.add(
        InlineKeyboardButton(
            text="📊 آمار ربات",
            callback_data="admin_stats"
        ),
        row=6
    )

    keyboard.add(
        InlineKeyboardButton(
            text="🔙 بازگشت",
            callback_data="back_home"
        ),
        row=7
    )

    return keyboard


# =========================================================
# پنل مدیریت کانال‌ها
# =========================================================

def channel_admin_panel():

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            text="➕ افزودن کانال",
            callback_data="add_channel"
        ),
        row=1
    )

    keyboard.add(
        InlineKeyboardButton(
            text="🗑️ حذف کانال",
            callback_data="remove_channel"
        ),
        row=2
    )

    keyboard.add(
        InlineKeyboardButton(
            text="📋 لیست کانال‌ها",
            callback_data="list_channels"
        ),
        row=3
    )

    keyboard.add(
        InlineKeyboardButton(
            text="🔙 بازگشت",
            callback_data="admin_back"
        ),
        row=4
    )

    return keyboard


# =========================================================
# پنل کدهای هدیه
# =========================================================

def gift_admin_panel():

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            text="➕ ساخت کد هدیه",
            callback_data="create_gift"
        ),
        row=1
    )

    keyboard.add(
        InlineKeyboardButton(
            text="📋 لیست کدها",
            callback_data="list_gifts"
        ),
        row=2
    )

    keyboard.add(
        InlineKeyboardButton(
            text="🔙 بازگشت",
            callback_data="admin_back"
        ),
        row=3
    )

    return keyboard


# =========================================================
# بررسی عضویت اجباری
# =========================================================

async def check_required_membership(user_id):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM required_channels"
    )

    channels = cursor.fetchall()

    conn.close()

    if not channels:
        return True, []

    not_joined = []

    for channel in channels:

        try:

            member = await bot.get_chat_member(
                channel["chat_id"],
                user_id
            )

            if not member or not member.is_member:
                not_joined.append(channel)

        except Exception as error:

            print(
                "Membership check error:",
                error
            )

            not_joined.append(channel)

    return len(not_joined) == 0, not_joined


# =========================================================
# پنل عضویت اجباری
# =========================================================

def required_membership_panel(channels):

    keyboard = InlineKeyboardMarkup()

    row = 1

    for channel in channels:

        link = channel["link"]

        if link:

            keyboard.add(
                InlineKeyboardButton(
                    text=f"📢 {channel['title']}",
                    url=link
                ),
                row=row
            )

            row += 1

    keyboard.add(
        InlineKeyboardButton(
            text="✅ بررسی عضویت",
            callback_data="check_membership"
        ),
        row=row
    )

    return keyboard


# =========================================================
# پیام خوش‌آمدگویی
# =========================================================

async def send_home(message):

    user = message.author

    save_user(user)

    is_member, channels = await check_required_membership(
        user.user_id
    )

    if not is_member:

        await message.reply(
            "🔒 برای استفاده از بلومی باید ابتدا "
            "در کانال‌های زیر عضو بشی:\n\n"
            "بعد از عضویت روی «بررسی عضویت» بزن 🌸",
            components=required_membership_panel(channels)
        )

        return

    await message.reply(
        "🌸✨ به ممبرگیر بلومی خوش اومدی!\n\n"
        "🪙 اینجا می‌تونی سکه جمع کنی\n"
        "👥 برای کانالت ممبر سفارش بدی\n"
        "🎁 کدهای هدیه استفاده کنی\n"
        "💰 سکه خریداری کنی\n\n"
        "یکی از گزینه‌های زیر رو انتخاب کن 👇",
        components=user_panel()
    )


# =========================================================
# آماده شدن بات
# =========================================================

@bot.event
async def on_ready():

    print("🌸 Blumie Bot is ready!")
    print("🗄️ Database loaded!")


# =========================================================
# دریافت پیام
# =========================================================

@bot.event
async def on_message(message: Message):

    if not message.content:
        return

    user = message.author

    save_user(user)

    text = message.content.strip()

    # ---------------------------------------------
    # دستور ID
    # ---------------------------------------------

    if text == "/id":

        await message.reply(
            f"🆔 User ID شما:\n\n"
            f"{user.user_id}"
        )

        return

    # ---------------------------------------------
    # دستور Start
    # ---------------------------------------------

    if text == "/start":

        await send_home(message)

        return

    # ---------------------------------------------
    # پنل مدیریت
    # ---------------------------------------------

    if text == "/admin":

        if user.user_id != ADMIN_ID:

            await message.reply(
                "⛔ شما اجازه دسترسی به پنل مدیریت را ندارید."
            )

            return

        await message.reply(
            "👑 پنل مدیریت بلومی\n\n"
            "یکی از بخش‌های زیر را انتخاب کن:",
            components=admin_panel()
        )

        return

    # =================================================
    # حالت‌های ورود اطلاعات ادمین
    # =================================================

    if user.user_id == ADMIN_ID:

        state = admin_states.get(user.user_id)

        # ---------------------------------------------
        # افزودن کانال
        # ---------------------------------------------

        if state == "waiting_channel":

            channel_input = text

            if not (
                channel_input.startswith("@")
                or channel_input.startswith("http://")
                or channel_input.startswith("https://")
            ):

                await message.reply(
                    "❌ لینک یا آیدی کانال درست نیست.\n\n"
                    "مثلاً:\n"
                    "@mychannel\n\n"
                    "یا:\n"
                    "https://ble.ir/mychannel"
                )

                return

            try:

                chat = await bot.get_chat(
                    channel_input
                )

                if not chat:

                    await message.reply(
                        "❌ کانال پیدا نشد.\n"
                        "مطمئن شو ربات به کانال دسترسی دارد."
                    )

                    return

                title = chat.title or "کانال بدون نام"

                username = chat.username or ""

                if username:

                    link = f"https://ble.ir/{username}"

                else:

                    link = channel_input

                conn = get_db()
                cursor = conn.cursor()

                try:

                    cursor.execute("""
                        INSERT INTO required_channels (
                            chat_id,
                            title,
                            username,
                            link
                        )
                        VALUES (?, ?, ?, ?)
                    """, (
                        str(chat.id),
                        title,
                        username,
                        link
                    ))

                    conn.commit()

                    await message.reply(
                        "✅ کانال با موفقیت اضافه شد!\n\n"
                        f"📢 {title}\n"
                        f"🔗 {link}"
                    )

                except sqlite3.IntegrityError:

                    await message.reply(
                        "⚠️ این کانال قبلاً اضافه شده است."
                    )

                finally:

                    conn.close()

                admin_states.pop(
                    user.user_id,
                    None
                )

                return

            except Exception as error:

                print(
                    "Add channel error:",
                    error
                )

                await message.reply(
                    "❌ نتونستم کانال رو پیدا کنم.\n\n"
                    "اول مطمئن شو ربات داخل کانال هست "
                    "و دسترسی مدیریتی مناسب دارد."
                )

                return

        # ---------------------------------------------
        # ساخت کد هدیه
        # ---------------------------------------------

        if state == "waiting_gift":

            parts = text.split()

            if len(parts) != 3:

                await message.reply(
                    "❌ فرمت اشتباهه.\n\n"
                    "اینطوری بفرست:\n\n"
                    "CODE 20 50\n\n"
                    "یعنی:\n"
                    "CODE = کد هدیه\n"
                    "20 = تعداد سکه\n"
                    "50 = حداکثر تعداد استفاده"
                )

                return

            code = parts[0].upper()

            try:

                coins = int(parts[1])
                max_users = int(parts[2])

                if coins <= 0 or max_users <= 0:

                    raise ValueError

            except ValueError:

                await message.reply(
                    "❌ تعداد سکه و تعداد کاربران "
                    "باید عدد مثبت باشند."
                )

                return

            conn = get_db()
            cursor = conn.cursor()

            try:

                cursor.execute("""
                    INSERT INTO gift_codes (
                        code,
                        coins,
                        max_users,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                """, (
                    code,
                    coins,
                    max_users,
                    datetime.now().isoformat()
                ))

                conn.commit()

                await message.reply(
                    "🎁 کد هدیه ساخته شد!\n\n"
                    f"🎟️ کد: {code}\n"
                    f"🪙 سکه: {coins}\n"
                    f"👥 ظرفیت: {max_users}"
                )

            except sqlite3.IntegrityError:

                await message.reply(
                    "❌ این کد قبلاً ساخته شده."
                )

            finally:

                conn.close()

            admin_states.pop(
                user.user_id,
                None
            )

            return


# =========================================================
# Callback ها
# =========================================================

@bot.event
async def on_callback(callback: CallbackQuery):

    data = callback.data

    if not data:
        return

    user = callback.from_user

    save_user(user)

    # =====================================================
    # بازگشت به خانه
    # =====================================================

    if data == "back_home":

        await callback.message.reply(
            "🌸 پنل اصلی بلومی:",
            components=user_panel()
        )

        return

    # =====================================================
    # بررسی عضویت
    # =====================================================

    if data == "check_membership":

        is_member, channels = await check_required_membership(
            user.user_id
        )

        if not is_member:

            await callback.message.reply(
                "❌ هنوز عضویتت کامل نشده.\n\n"
                "اول در همه کانال‌ها عضو شو و دوباره "
                "روی بررسی عضویت بزن.",
                components=required_membership_panel(channels)
            )

            return

        await callback.message.reply(
            "✅ عضویتت تأیید شد!\n\n"
            "🌸 حالا می‌تونی از بلومی استفاده کنی.",
            components=user_panel()
        )

        return

    # =====================================================
    # سکه‌های من
    # =====================================================

    if data == "user_coins":

        user_data = get_user(user.user_id)

        coins = user_data["coins"]

        await callback.message.reply(
            "🪙 موجودی سکه شما:\n\n"
            f"💰 {coins} سکه",
            components=user_panel()
        )

        return

    # =====================================================
    # جمع‌آوری سکه
    # =====================================================

    if data == "collect_coins":

        user_data = get_user(user.user_id)

        today = str(date.today())

        if user_data["last_daily"] == today:

            await callback.message.reply(
                "🎁 سکه روزانه امروزت رو قبلاً گرفتی!\n\n"
                "⏰ فردا دوباره می‌تونی ۵ سکه بگیری.",
                components=user_panel()
            )

            return

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE users
            SET coins = coins + 5,
                total_earned = total_earned + 5,
                last_daily = ?
            WHERE user_id = ?
        """, (
            today,
            user.user_id
        ))

        conn.commit()
        conn.close()

        await callback.message.reply(
            "🎉 تبریک!\n\n"
            "🪙 ۵ سکه روزانه به حسابت اضافه شد.",
            components=user_panel()
        )

        return

    # =====================================================
    # سفارش ممبر
    # =====================================================

    if data == "member_order":

        await callback.message.reply(
            "👥 سفارش ممبر\n\n"
            "📌 قیمت فعلی:\n"
            "هر ممبر = ۲ سکه\n\n"
            "🛠️ بخش ثبت سفارش در مرحله بعد فعال می‌شود.",
            components=user_panel()
        )

        return

    # =====================================================
    # خرید سکه
    # =====================================================

    if data == "buy_coins":

        await callback.message.reply(
            "💰 خرید سکه\n\n"
            "🪙 قیمت هر سکه: ۲۰۰ تومان\n"
            "🔹 حداقل خرید: ۱۰۰ سکه\n"
            "🔹 حداکثر خرید: ۵۰۰ سکه\n\n"
            "🛠️ پرداخت آنلاین در مرحله بعد فعال می‌شود.",
            components=user_panel()
        )

        return

    # =====================================================
    # کد هدیه
    # =====================================================

    if data == "gift_code":

        await callback.message.reply(
            "🎟️ کد هدیه\n\n"
            "کد هدیه‌ای که از بلومی گرفتی رو "
            "به صورت پیام برای ربات ارسال کن.\n\n"
            "مثال:\n"
            "BLUMIE20"
        )

        return

    # =====================================================
    # حساب من
    # =====================================================

    if data == "my_account":

        user_data = get_user(user.user_id)

        await callback.message.reply(
            "👤 حساب کاربری\n\n"
            f"🆔 شناسه: {user.user_id}\n"
            f"👤 نام: {user_data['first_name']}\n"
            f"🪙 سکه: {user_data['coins']}",
            components=user_panel()
        )

        return

    # =====================================================
    # فعالیت من
    # =====================================================

    if data == "my_activity":

        user_data = get_user(user.user_id)

        await callback.message.reply(
            "📊 فعالیت من\n\n"
            f"🪙 کل سکه‌های دریافت‌شده: "
            f"{user_data['total_earned']}\n\n"
            f"💸 کل سکه‌های مصرف‌شده: "
            f"{user_data['total_spent']}",
            components=user_panel()
        )

        return

    # =====================================================
    # پشتیبانی
    # =====================================================

    if data == "support":

        await callback.message.reply(
            "📞 پشتیبانی بلومی\n\n"
            "اگر مشکلی داشتی، پیام خودت رو برای "
            "پشتیبانی ارسال کن.\n\n"
            "🛠️ سیستم تیکت پشتیبانی در مرحله بعد "
            "تکمیل می‌شود.",
            components=user_panel()
        )

        return

    # =====================================================
    # بررسی ادمین
    # =====================================================

    if user.user_id != ADMIN_ID:

        if data.startswith("admin_") or data in [
            "add_channel",
            "remove_channel",
            "list_channels",
            "create_gift",
            "list_gifts"
        ]:

            await callback.message.reply(
                "⛔ دسترسی غیرمجاز."
            )

            return

    # =====================================================
    # پنل مدیریت
    # =====================================================

    if data == "admin_back":

        await callback.message.reply(
            "👑 پنل مدیریت:",
            components=admin_panel()
        )

        return

    # =====================================================
    # مدیریت عضویت اجباری
    # =====================================================

    if data == "admin_channels":

        await callback.message.reply(
            "📢 مدیریت عضویت اجباری\n\n"
            "از این قسمت می‌تونی کانال‌هایی که "
            "کاربر باید عضو آن‌ها باشد را مدیریت کنی.",
            components=channel_admin_panel()
        )

        return

    # =====================================================
    # افزودن کانال
    # =====================================================

    if data == "add_channel":

        admin_states[user.user_id] = "waiting_channel"

        await callback.message.reply(
            "➕ افزودن کانال\n\n"
            "لینک یا آیدی کانال رو بفرست.\n\n"
            "مثال:\n"
            "@mychannel\n\n"
            "یا:\n"
            "https://ble.ir/mychannel"
        )

        return

    # =====================================================
    # لیست کانال‌ها
    # =====================================================

    if data == "list_channels":

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM required_channels"
        )

        channels = cursor.fetchall()

        conn.close()

        if not channels:

            await callback.message.reply(
                "📋 هنوز هیچ کانالی برای عضویت اجباری "
                "ثبت نشده.",
                components=channel_admin_panel()
            )

            return

        text = "📋 کانال‌های عضویت اجباری:\n\n"

        for index, channel in enumerate(
            channels,
            start=1
        ):

            text += (
                f"{index}. 📢 {channel['title']}\n"
                f"🔗 {channel['link']}\n\n"
            )

        await callback.message.reply(
            text,
            components=channel_admin_panel()
        )

        return

    # =====================================================
    # حذف کانال
    # =====================================================

    if data == "remove_channel":

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM required_channels"
        )

        channels = cursor.fetchall()

        conn.close()

        if not channels:

            await callback.message.reply(
                "🗑️ هیچ کانالی برای حذف وجود ندارد.",
                components=channel_admin_panel()
            )

            return

        keyboard = InlineKeyboardMarkup()

        for channel in channels:

            keyboard.add(
                InlineKeyboardButton(
                    text=f"🗑️ {channel['title']}",
                    callback_data=f"delete_channel:{channel['id']}"
                )
            )

        keyboard.add(
            InlineKeyboardButton(
                text="🔙 بازگشت",
                callback_data="admin_channels"
            ),
            row=len(channels) + 1
        )

        await callback.message.reply(
            "🗑️ کانالی که می‌خوای حذف کنی رو انتخاب کن:",
            components=keyboard
        )

        return

    # =====================================================
    # حذف یک کانال
    # =====================================================

    if data.startswith("delete_channel:"):

        channel_id = data.split(":")[1]

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT title FROM required_channels WHERE id = ?",
            (channel_id,)
        )

        channel = cursor.fetchone()

        if channel:

            cursor.execute(
                "DELETE FROM required_channels WHERE id = ?",
                (channel_id,)
            )

            conn.commit()

        conn.close()

        if channel:

            await callback.message.reply(
                f"✅ کانال «{channel['title']}» حذف شد.",
                components=channel_admin_panel()
            )

        else:

            await callback.message.reply(
                "❌ کانال پیدا نشد.",
                components=channel_admin_panel()
            )

        return

    # =====================================================
    # مدیریت سکه
    # =====================================================

    if data == "admin_coins":

        await callback.message.reply(
            "🪙 مدیریت سکه\n\n"
            "سیستم کامل مدیریت سکه در حال آماده‌سازی است.\n\n"
            "قیمت فعلی:\n"
            "🪙 هر سکه = ۲۰۰ تومان\n"
            "🔹 حداقل خرید = ۱۰۰ سکه\n"
            "🔹 حداکثر خرید = ۵۰۰ سکه",
            components=admin_panel()
        )

        return

    # =====================================================
    # مدیریت کد هدیه
    # =====================================================

    if data == "admin_gifts":

        await callback.message.reply(
            "🎁 مدیریت کدهای هدیه",
            components=gift_admin_panel()
        )

        return

    # =====================================================
    # ساخت کد هدیه
    # =====================================================

    if data == "create_gift":

        admin_states[user.user_id] = "waiting_gift"

        await callback.message.reply(
            "➕ ساخت کد هدیه\n\n"
            "فرمت زیر رو بفرست:\n\n"
            "CODE 20 50\n\n"
            "یعنی:\n"
            "🎟️ CODE = نام کد\n"
            "🪙 20 = تعداد سکه\n"
            "👥 50 = حداکثر تعداد استفاده"
        )

        return

    # =====================================================
    # لیست کدهای هدیه
    # =====================================================

    if data == "list_gifts":

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM gift_codes ORDER BY id DESC"
        )

        gifts = cursor.fetchall()

        conn.close()

        if not gifts:

            await callback.message.reply(
                "🎁 هنوز هیچ کد هدیه‌ای ساخته نشده.",
                components=gift_admin_panel()
            )

            return

        text = "🎁 کدهای هدیه:\n\n"

        for gift in gifts:

            status = (
                "🟢 فعال"
                if gift["active"]
                else "🔴 غیرفعال"
            )

            text += (
                f"🎟️ {gift['code']}\n"
                f"🪙 {gift['coins']} سکه\n"
                f"👥 {gift['used_users']}/{gift['max_users']}\n"
                f"{status}\n\n"
            )

        await callback.message.reply(
            text,
            components=gift_admin_panel()
        )

        return

    # =====================================================
    # استفاده از کد هدیه
    # =====================================================

    if data == "admin_orders":

        await callback.message.reply(
            "👥 مدیریت سفارش‌ها\n\n"
            "بخش سفارش‌ها بعد از فعال شدن "
            "سیستم ثبت سفارش تکمیل می‌شود.",
            components=admin_panel()
        )

        return

    # =====================================================
    # کاربران
    # =====================================================

    if data == "admin_users":

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) AS count FROM users"
        )

        count = cursor.fetchone()["count"]

        conn.close()

        await callback.message.reply(
            "👤 کاربران بلومی\n\n"
            f"👥 تعداد کاربران ثبت‌شده: {count}",
            components=admin_panel()
        )

        return

    # =====================================================
    # آمار
    # =====================================================

    if data == "admin_stats":

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) AS count FROM users"
        )
        users = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COUNT(*) AS count FROM required_channels"
        )
        channels = cursor.fetchone()["count"]

        cursor.execute(
            "SELECT COALESCE(SUM(coins), 0) AS total FROM users"
        )
        coins = cursor.fetchone()["total"]

        cursor.execute(
            "SELECT COUNT(*) AS count FROM orders"
        )
        orders = cursor.fetchone()["count"]

        conn.close()

        await callback.message.reply(
            "📊 آمار بلومی\n\n"
            f"👥 کاربران: {users}\n"
            f"📢 کانال‌های اجباری: {channels}\n"
            f"🪙 مجموع سکه کاربران: {coins}\n"
            f"👥 سفارش‌ها: {orders}",
            components=admin_panel()
        )

        return


# =========================================================
# اجرای برنامه
# =========================================================

if __name__ == "__main__":

    web_thread = threading.Thread(
        target=run_web_server,
        daemon=True
    )

    web_thread.start()

    print("🌐 Render web server started!")

    bot.run()
