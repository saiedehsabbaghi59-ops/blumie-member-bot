import os
import sqlite3
import threading
from datetime import datetime, date

from flask import Flask

from bale import (
    Bot,
    Message,
    MenuKeyboardMarkup,
    MenuKeyboardButton
)


# =========================================================
# تنظیمات
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

# آیدی ادمین خودت
ADMIN_ID = 652485302

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN در Render تنظیم نشده است!")


# =========================================================
# Flask برای Render
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
# Bot
# =========================================================

bot = Bot(token=BOT_TOKEN)


# =========================================================
# Database
# =========================================================

DB_NAME = "blumie.db"


def get_db():
    conn = sqlite3.connect(
        DB_NAME,
        check_same_thread=False,
        timeout=30
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

    # کانال‌های عضویت اجباری اصلی
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS required_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            title TEXT,
            username TEXT,
            link TEXT
        )
    """)

    # کانال‌های کمپین جمع‌آوری سکه
    # این کانال‌ها همان کانال‌هایی هستند که سفارش کاربران
    # در آینده می‌تواند آنها را وارد این لیست کند.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS earning_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            title TEXT,
            username TEXT,
            link TEXT,
            reward INTEGER DEFAULT 1,
            active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    # ثبت اینکه هر کاربر بابت کدام کانال سکه گرفته
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channel_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id INTEGER,
            reward INTEGER,
            created_at TEXT,
            UNIQUE(user_id, channel_id)
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

    # استفاده از کد هدیه
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
            channel_link TEXT,
            channel_id TEXT,
            channel_title TEXT,
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
# حالت‌های موقت کاربران
# =========================================================

user_states = {}


# =========================================================
# ذخیره کاربر
# =========================================================

def save_user(user):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user.user_id,)
    )

    exists = cursor.fetchone()

    first_name = user.first_name or ""
    username = user.username or ""

    if not exists:

        cursor.execute("""
            INSERT INTO users (
                user_id,
                first_name,
                username,
                coins,
                total_earned,
                total_spent,
                joined_at,
                last_daily
            )
            VALUES (?, ?, ?, 0, 0, 0, ?, NULL)
        """, (
            user.user_id,
            first_name,
            username,
            datetime.now().isoformat()
        ))

    else:

        cursor.execute("""
            UPDATE users
            SET first_name = ?,
                username = ?
            WHERE user_id = ?
        """, (
            first_name,
            username,
            user.user_id
        ))

    conn.commit()
    conn.close()


# =========================================================
# گرفتن اطلاعات کاربر
# =========================================================

def get_user(user_id):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user_id,)
    )

    result = cursor.fetchone()

    conn.close()

    return result


# =========================================================
# اضافه کردن سکه
# =========================================================

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


# =========================================================
# کم کردن سکه
# =========================================================

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
# منوی اصلی پایین چت
# =========================================================

def main_menu():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton("🪙 سکه‌های من")
    )

    keyboard.add(
        MenuKeyboardButton("🎁 جمع‌آوری سکه")
    )

    keyboard.add(
        MenuKeyboardButton("👥 سفارش ممبر")
    )

    keyboard.add(
        MenuKeyboardButton("💰 خرید سکه")
    )

    keyboard.add(
        MenuKeyboardButton("🎟️ کد هدیه")
    )

    keyboard.add(
        MenuKeyboardButton("👤 حساب من")
    )

    keyboard.add(
        MenuKeyboardButton("📊 فعالیت من")
    )

    keyboard.add(
        MenuKeyboardButton("📞 پشتیبانی")
    )

    return keyboard


# =========================================================
# منوی مدیریت
# =========================================================

def admin_menu():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton("📢 عضویت اجباری")
    )

    keyboard.add(
        MenuKeyboardButton("📣 کانال‌های کسب سکه")
    )

    keyboard.add(
        MenuKeyboardButton("🪙 مدیریت سکه")
    )

    keyboard.add(
        MenuKeyboardButton("🎁 مدیریت کد هدیه")
    )

    keyboard.add(
        MenuKeyboardButton("👥 سفارش‌ها")
    )

    keyboard.add(
        MenuKeyboardButton("👤 کاربران")
    )

    keyboard.add(
        MenuKeyboardButton("📊 آمار")
    )

    keyboard.add(
        MenuKeyboardButton("🔙 منوی اصلی")
    )

    return keyboard


# =========================================================
# منوی عضویت اجباری
# =========================================================

def required_admin_menu():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton("➕ افزودن عضویت اجباری")
    )

    keyboard.add(
        MenuKeyboardButton("🗑️ حذف عضویت اجباری")
    )

    keyboard.add(
        MenuKeyboardButton("📋 لیست عضویت اجباری")
    )

    keyboard.add(
        MenuKeyboardButton("🔙 پنل مدیریت")
    )

    return keyboard


# =========================================================
# منوی کانال‌های کسب سکه
# =========================================================

def earning_admin_menu():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton("➕ افزودن کانال کسب سکه")
    )

    keyboard.add(
        MenuKeyboardButton("🗑️ حذف کانال کسب سکه")
    )

    keyboard.add(
        MenuKeyboardButton("📋 لیست کانال‌های کسب سکه")
    )

    keyboard.add(
        MenuKeyboardButton("🔙 پنل مدیریت")
    )

    return keyboard


# =========================================================
# منوی کد هدیه
# =========================================================

def gift_admin_menu():

    keyboard = MenuKeyboardMarkup()

    keyboard.add(
        MenuKeyboardButton("➕ ساخت کد هدیه")
    )

    keyboard.add(
        MenuKeyboardButton("📋 لیست کدهای هدیه")
    )

    keyboard.add(
        MenuKeyboardButton("🔙 پنل مدیریت")
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
                "Required membership error:",
                error
            )

            not_joined.append(channel)

    return len(not_joined) == 0, not_joined


# =========================================================
# نمایش کانال‌های عضویت اجباری
# =========================================================

def required_text(channels):

    text = (
        "🔒 برای استفاده از بلومی باید ابتدا "
        "در کانال‌های زیر عضو بشی:\n\n"
    )

    for index, channel in enumerate(channels, 1):

        text += (
            f"{index}. 📢 {channel['title']}\n"
            f"🔗 {channel['link']}\n\n"
        )

    text += (
        "بعد از عضویت در همه کانال‌ها، "
        "کلمه «بررسی عضویت» رو بفرست."
    )

    return text


# =========================================================
# صفحه اصلی
# =========================================================

async def send_home(message):

    user = message.author

    save_user(user)

    is_member, channels = await check_required_membership(
        user.user_id
    )

    if not is_member:

        await message.reply(
            required_text(channels)
        )

        return

    await message.reply(
        "🌸✨ به ممبرگیر بلومی خوش اومدی!\n\n"
        "🪙 سکه جمع کن\n"
        "👥 برای کانالت ممبر سفارش بده\n"
        "🎁 کد هدیه استفاده کن\n"
        "💰 سکه بخر\n\n"
        "از منوی پایین چت استفاده کن 👇",
        components=main_menu()
    )


# =========================================================
# آماده شدن
# =========================================================

@bot.event
async def on_ready():

    print("================================")
    print("🌸 BLUMIE BOT IS READY!")
    print("👑 ADMIN ID:", ADMIN_ID)
    print("🗄️ DATABASE: OK")
    print("================================")


# =========================================================
# پیام‌ها
# =========================================================

@bot.event
async def on_message(message: Message):

    if not message.content:
        return

    user = message.author

    save_user(user)

    text = message.content.strip()

    print(
        f"Message from {user.user_id}: {text}"
    )

    # =====================================================
    # /start
    # =====================================================

    if text == "/start":

        user_states.pop(
            user.user_id,
            None
        )

        await send_home(message)

        return

    # =====================================================
    # /id
    # =====================================================

    if text == "/id":

        await message.reply(
            f"🆔 User ID شما:\n\n"
            f"{user.user_id}"
        )

        return

    # =====================================================
    # /admin
    # =====================================================

    if text == "/admin":

        if user.user_id != ADMIN_ID:

            await message.reply(
                "⛔ شما اجازه دسترسی به پنل مدیریت را ندارید."
            )

            return

        user_states.pop(
            user.user_id,
            None
        )

        await message.reply(
            "👑 پنل مدیریت بلومی\n\n"
            "خوش اومدی مدیر 🌸\n"
            "یکی از گزینه‌های پایین رو انتخاب کن:",
            components=admin_menu()
        )

        return

    # =====================================================
    # بررسی عضویت
    # =====================================================

    if text == "بررسی عضویت":

        is_member, channels = await check_required_membership(
            user.user_id
        )

        if not is_member:

            await message.reply(
                "❌ هنوز عضویتت کامل نشده.\n\n"
                + required_text(channels)
            )

            return

        await message.reply(
            "✅ عضویتت تأیید شد!\n\n"
            "🌸 حالا می‌تونی از بلومی استفاده کنی.",
            components=main_menu()
        )

        return

    # =====================================================
    # اگر کاربر در حالت خاصی است
    # =====================================================

    state = user_states.get(user.user_id)

    # =====================================================
    # ورود کانال سفارش
    # =====================================================

    if state == "order_channel":

        channel_input = text

        if not (
            channel_input.startswith("@")
            or channel_input.startswith("http://")
            or channel_input.startswith("https://")
        ):

            await message.reply(
                "❌ آیدی یا لینک کانالت درست نیست.\n\n"
                "مثال:\n"
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
                    "❌ کانال پیدا نشد."
                )

                return

            user_states[user.user_id] = {
                "state": "order_members",
                "channel_input": channel_input,
                "channel_id": str(chat.id),
                "channel_title": chat.title or "کانال"
            }

            await message.reply(
                "👥 خیلی خوب!\n\n"
                "حالا تعداد ممبری که می‌خوای سفارش بدی رو بفرست.\n\n"
                "مثلاً:\n"
                "100"
            )

        except Exception as error:

            print(
                "Order channel error:",
                error
            )

            await message.reply(
                "❌ نتونستم کانالت رو پیدا کنم.\n\n"
                "مطمئن شو لینک یا آیدی کانال درست باشه "
                "و ربات دسترسی لازم رو داشته باشه."
            )

        return

    # =====================================================
    # تعداد ممبر سفارش
    # =====================================================

    if isinstance(state, dict) and state.get("state") == "order_members":

        try:

            members = int(text)

            if members <= 0:
                raise ValueError

        except ValueError:

            await message.reply(
                "❌ تعداد ممبر باید یک عدد مثبت باشه."
            )

            return

        coins = members * 2

        user_data = get_user(
            user.user_id
        )

        if user_data["coins"] < coins:

            await message.reply(
                "❌ سکه کافی نداری.\n\n"
                f"👥 تعداد ممبر: {members}\n"
                f"🪙 هزینه: {coins} سکه\n"
                f"💰 موجودی تو: {user_data['coins']} سکه\n\n"
                "اول سکه جمع کن یا سکه بخر.",
                components=main_menu()
            )

            user_states.pop(
                user.user_id,
                None
            )

            return

        # کم کردن سکه
        success = remove_coins(
            user.user_id,
            coins
        )

        if not success:

            await message.reply(
                "❌ انجام سفارش ممکن نشد؛ "
                "موجودی سکه کافی نیست."
            )

            user_states.pop(
                user.user_id,
                None
            )

            return

        channel_input = state["channel_input"]
        channel_id = state["channel_id"]
        channel_title = state["channel_title"]

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO orders (
                user_id,
                channel_link,
                channel_id,
                channel_title,
                members,
                coins,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user.user_id,
            channel_input,
            channel_id,
            channel_title,
            members,
            coins,
            "pending",
            datetime.now().isoformat()
        ))

        order_id = cursor.lastrowid

        # =================================================
        # کانال سفارش‌دهنده وارد لیست کسب سکه می‌شود
        # =================================================

        try:

            cursor.execute("""
                INSERT OR IGNORE INTO earning_channels (
                    chat_id,
                    title,
                    username,
                    link,
                    reward,
                    active,
                    created_at
                )
                VALUES (?, ?, ?, ?, 1, 1, ?)
            """, (
                channel_id,
                channel_title,
                "",
                channel_input,
                datetime.now().isoformat()
            ))

        except Exception as error:

            print(
                "Add earning channel error:",
                error
            )

        conn.commit()
        conn.close()

        user_states.pop(
            user.user_id,
            None
        )

        await message.reply(
            "🎉 سفارش با موفقیت ثبت شد!\n\n"
            f"🆔 شماره سفارش: {order_id}\n"
            f"📢 کانال: {channel_title}\n"
            f"👥 تعداد ممبر: {members}\n"
            f"🪙 هزینه: {coins} سکه\n\n"
            "⏳ وضعیت سفارش: در انتظار بررسی\n\n"
            "📣 کانال تو هم به لیست جمع‌آوری سکه "
            "اضافه شد تا کاربران دیگر با عضویت در آن "
            "بتوانند سکه بگیرند.",
            components=main_menu()
        )

        return

    # =====================================================
    # افزودن کانال عضویت اجباری
    # =====================================================

    if user.user_id == ADMIN_ID and state == "required_add":

        channel_input = text

        if not (
            channel_input.startswith("@")
            or channel_input.startswith("http://")
            or channel_input.startswith("https://")
        ):

            await message.reply(
                "❌ لینک یا آیدی کانال درست نیست."
            )

            return

        try:

            chat = await bot.get_chat(
                channel_input
            )

            if not chat:

                await message.reply(
                    "❌ کانال پیدا نشد."
                )

                return

            title = chat.title or "کانال"
            username = chat.username or ""
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
                    "✅ کانال عضویت اجباری اضافه شد!\n\n"
                    f"📢 {title}\n"
                    f"🔗 {link}",
                    components=required_admin_menu()
                )

            except sqlite3.IntegrityError:

                await message.reply(
                    "⚠️ این کانال قبلاً وجود دارد.",
                    components=required_admin_menu()
                )

            finally:

                conn.close()

        except Exception as error:

            print(
                "Required channel error:",
                error
            )

            await message.reply(
                "❌ نتونستم کانال رو پیدا کنم."
            )

        user_states.pop(
            user.user_id,
            None
        )

        return

    # =====================================================
    # افزودن کانال کسب سکه توسط ادمین
    # =====================================================

    if user.user_id == ADMIN_ID and state == "earning_add":

        channel_input = text

        if not (
            channel_input.startswith("@")
            or channel_input.startswith("http://")
            or channel_input.startswith("https://")
        ):

            await message.reply(
                "❌ لینک یا آیدی کانال درست نیست."
            )

            return

        try:

            chat = await bot.get_chat(
                channel_input
            )

            if not chat:

                await message.reply(
                    "❌ کانال پیدا نشد."
                )

                return

            title = chat.title or "کانال"
            username = chat.username or ""

            conn = get_db()
            cursor = conn.cursor()

            try:

                cursor.execute("""
                    INSERT INTO earning_channels (
                        chat_id,
                        title,
                        username,
                        link,
                        reward,
                        active,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, 1, 1, ?)
                """, (
                    str(chat.id),
                    title,
                    username,
                    channel_input,
                    datetime.now().isoformat()
                ))

                conn.commit()

                await message.reply(
                    "✅ کانال کسب سکه اضافه شد!\n\n"
                    f"📢 {title}\n"
                    f"🪙 پاداش عضویت: ۱ سکه",
                    components=earning_admin_menu()
                )

            except sqlite3.IntegrityError:

                await message.reply(
                    "⚠️ این کانال قبلاً وجود دارد.",
                    components=earning_admin_menu()
                )

            finally:

                conn.close()

        except Exception as error:

            print(
                "Earning channel error:",
                error
            )

            await message.reply(
                "❌ نتونستم کانال رو پیدا کنم."
            )

        user_states.pop(
            user.user_id,
            None
        )

        return

    # =====================================================
    # ساخت کد هدیه
    # =====================================================

    if user.user_id == ADMIN_ID and state == "gift_add":

        parts = text.split()

        if len(parts) != 3:

            await message.reply(
                "❌ فرمت اشتباهه.\n\n"
                "مثال:\n"
                "BLUMIE20 20 50\n\n"
                "BLUMIE20 = کد\n"
                "20 = سکه\n"
                "50 = ظرفیت استفاده"
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
                "❌ تعداد سکه و ظرفیت باید عدد مثبت باشند."
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
                    used_users,
                    active,
                    created_at
                )
                VALUES (?, ?, ?, 0, 1, ?)
            """, (
                code,
                coins,
                max_users,
                datetime.now().isoformat()
            ))

            conn.commit()

            await message.reply(
                "🎉 کد هدیه ساخته شد!\n\n"
                f"🎟️ کد: {code}\n"
                f"🪙 سکه: {coins}\n"
                f"👥 ظرفیت: {max_users}",
                components=gift_admin_menu()
            )

        except sqlite3.IntegrityError:

            await message.reply(
                "❌ این کد قبلاً ساخته شده.",
                components=gift_admin_menu()
            )

        finally:

            conn.close()

        user_states.pop(
            user.user_id,
            None
        )

        return

    # =====================================================
    # استفاده از کد هدیه
    # =====================================================

    if state is None and text not in [
        "🪙 سکه‌های من",
        "🎁 جمع‌آوری سکه",
        "👥 سفارش ممبر",
        "💰 خرید سکه",
        "🎟️ کد هدیه",
        "👤 حساب من",
        "📊 فعالیت من",
        "📞 پشتیبانی",
        "📢 عضویت اجباری",
        "📣 کانال‌های کسب سکه",
        "🪙 مدیریت سکه",
        "🎁 مدیریت کد هدیه",
        "👥 سفارش‌ها",
        "👤 کاربران",
        "📊 آمار",
        "🔙 منوی اصلی"
    ]:

        # اگر متن شبیه کد هدیه بود
        code = text.upper()

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM gift_codes
            WHERE code = ?
              AND active = 1
        """, (
            code,
        ))

        gift = cursor.fetchone()

        if gift:

            cursor.execute("""
                SELECT id
                FROM gift_usages
                WHERE code = ?
                  AND user_id = ?
            """, (
                code,
                user.user_id
            ))

            already_used = cursor.fetchone()

            if already_used:

                conn.close()

                await message.reply(
                    "⚠️ این کد هدیه رو قبلاً استفاده کردی.",
                    components=main_menu()
                )

                return

            if gift["used_users"] >= gift["max_users"]:

                conn.close()

                await message.reply(
                    "❌ ظرفیت این کد هدیه تکمیل شده.",
                    components=main_menu()
                )

                return

            cursor.execute("""
                INSERT INTO gift_usages (
                    code,
                    user_id
                )
                VALUES (?, ?)
            """, (
                code,
                user.user_id
            ))

            cursor.execute("""
                UPDATE gift_codes
                SET used_users = used_users + 1
                WHERE code = ?
            """, (
                code,
            ))

            cursor.execute("""
                UPDATE users
                SET coins = coins + ?,
                    total_earned = total_earned + ?
                WHERE user_id = ?
            """, (
                gift["coins"],
                gift["coins"],
                user.user_id
            ))

            conn.commit()
            conn.close()

            await message.reply(
                "🎉 کد هدیه با موفقیت فعال شد!\n\n"
                f"🎟️ کد: {code}\n"
                f"🪙 {gift['coins']} سکه به حسابت اضافه شد.",
                components=main_menu()
            )

            return

        conn.close()

    # =====================================================
    # منوی اصلی کاربر
    # =====================================================

    if text == "🪙 سکه‌های من":

        user_data = get_user(
            user.user_id
        )

        await message.reply(
            "🪙 موجودی شما:\n\n"
            f"💰 {user_data['coins']} سکه",
            components=main_menu()
        )

        return

    # =====================================================
    # جمع‌آوری سکه
    # =====================================================

    if text == "🎁 جمع‌آوری سکه":

        is_member, channels = await check_required_membership(
            user.user_id
        )

        if not is_member:

            await message.reply(
                "🔒 اول باید عضویت اجباری رو کامل کنی.\n\n"
                + required_text(channels)
            )

            return

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM earning_channels
            WHERE active = 1
        """)

        earning_channels = cursor.fetchall()

        if not earning_channels:

            conn.close()

            await message.reply(
                "🎁 فعلاً کانالی برای جمع‌آوری سکه وجود نداره.\n\n"
                "بعداً دوباره امتحان کن.",
                components=main_menu()
            )

            return

        total_reward = 0
        successful_channels = 0

        for channel in earning_channels:

            try:

                member = await bot.get_chat_member(
                    channel["chat_id"],
                    user.user_id
                )

                if member and member.is_member:

                    cursor.execute("""
                        SELECT id
                        FROM channel_rewards
                        WHERE user_id = ?
                          AND channel_id = ?
                    """, (
                        user.user_id,
                        channel["id"]
                    ))

                    already_rewarded = cursor.fetchone()

                    if not already_rewarded:

                        reward = channel["reward"]

                        cursor.execute("""
                            INSERT INTO channel_rewards (
                                user_id,
                                channel_id,
                                reward,
                                created_at
                            )
                            VALUES (?, ?, ?, ?)
                        """, (
                            user.user_id,
                            channel["id"],
                            reward,
                            datetime.now().isoformat()
                        ))

                        cursor.execute("""
                            UPDATE users
                            SET coins = coins + ?,
                                total_earned = total_earned + ?
                            WHERE user_id = ?
                        """, (
                            reward,
                            reward,
                            user.user_id
                        ))

                        total_reward += reward
                        successful_channels += 1

            except Exception as error:

                print(
                    "Earning channel check error:",
                    error
                )

        conn.commit()
        conn.close()

        if total_reward > 0:

            await message.reply(
                "🎉 سکه‌ها با موفقیت اضافه شدند!\n\n"
                f"📢 تعداد کانال‌های جدید: {successful_channels}\n"
                f"🪙 سکه دریافت‌شده: {total_reward}",
                components=main_menu()
            )

        else:

            await message.reply(
                "ℹ️ این بار سکه جدیدی برایت پیدا نشد.\n\n"
                "اگر قبلاً سکه کانال‌ها رو گرفتی، "
                "دوباره برای همان کانال سکه نمی‌گیری.",
                components=main_menu()
            )

        return

    # =====================================================
    # سفارش ممبر
    # =====================================================

    if text == "👥 سفارش ممبر":

        user_states[user.user_id] = "order_channel"

        await message.reply(
            "👥 ثبت سفارش ممبر\n\n"
            "📌 قیمت:\n"
            "هر ممبر = ۲ سکه\n\n"
            "🔗 اول لینک یا آیدی کانالت رو بفرست.\n\n"
            "مثال:\n"
            "@mychannel"
        )

        return

    # =====================================================
    # خرید سکه
    # =====================================================

    if text == "💰 خرید سکه":

        await message.reply(
            "💰 خرید سکه\n\n"
            "🪙 قیمت هر سکه: ۲۰۰ تومان\n\n"
            "🔹 حداقل خرید: ۱۰۰ سکه\n"
            "💵 قیمت: ۲۰٬۰۰۰ تومان\n\n"
            "🔹 حداکثر خرید: ۵۰۰ سکه\n"
            "💵 قیمت: ۱۰۰٬۰۰۰ تومان\n\n"
            "⚠️ در این نسخه پرداخت آنلاین هنوز فعال نشده.",
            components=main_menu()
        )

        return

    # =====================================================
    # کد هدیه
    # =====================================================

    if text == "🎟️ کد هدیه":

        await message.reply(
            "🎟️ کد هدیه\n\n"
            "کد هدیه‌ات رو همینجا ارسال کن.\n\n"
            "مثال:\n"
            "BLUMIE20"
        )

        return

    # =====================================================
    # حساب من
    # =====================================================

    if text == "👤 حساب من":

        user_data = get_user(
            user.user_id
        )

        await message.reply(
            "👤 حساب کاربری\n\n"
            f"🆔 شناسه: {user.user_id}\n"
            f"👤 نام: {user_data['first_name']}\n"
            f"🪙 سکه: {user_data['coins']}",
            components=main_menu()
        )

        return

    # =====================================================
    # فعالیت
    # =====================================================

    if text == "📊 فعالیت من":

        user_data = get_user(
            user.user_id
        )

        await message.reply(
            "📊 فعالیت من\n\n"
            f"🪙 کل سکه‌های دریافت‌شده: "
            f"{user_data['total_earned']}\n\n"
            f"💸 کل سکه‌های مصرف‌شده: "
            f"{user_data['total_spent']}",
            components=main_menu()
        )

        return

    # =====================================================
    # پشتیبانی
    # =====================================================

    if text == "📞 پشتیبانی":

        await message.reply(
            "📞 پشتیبانی بلومی\n\n"
            "پیامت رو برای پشتیبانی ارسال کن.\n\n"
            "🛠️ سیستم تیکت در نسخه بعدی تکمیل می‌شود.",
            components=main_menu()
        )

        return

    # =====================================================
    # ================= پنل مدیریت ========================
    # =====================================================

    if user.user_id == ADMIN_ID:

        # -------------------------------------------------
        # عضویت اجباری
        # -------------------------------------------------

        if text == "📢 عضویت اجباری":

            await message.reply(
                "📢 مدیریت عضویت اجباری",
                components=required_admin_menu()
            )

            return

        if text == "➕ افزودن عضویت اجباری":

            user_states[user.user_id] = "required_add"

            await message.reply(
                "➕ افزودن کانال عضویت اجباری\n\n"
                "لینک یا آیدی کانال رو بفرست.\n\n"
                "مثال:\n"
                "@mychannel"
            )

            return

        if text == "📋 لیست عضویت اجباری":

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM required_channels"
            )

            channels = cursor.fetchall()

            conn.close()

            if not channels:

                await message.reply(
                    "📋 هیچ کانال عضویت اجباری ثبت نشده.",
                    components=required_admin_menu()
                )

                return

            result = "📋 کانال‌های عضویت اجباری:\n\n"

            for index, channel in enumerate(channels, 1):

                result += (
                    f"{index}. {channel['title']}\n"
                    f"🔗 {channel['link']}\n\n"
                )

            await message.reply(
                result,
                components=required_admin_menu()
            )

            return

        if text == "🗑️ حذف عضویت اجباری":

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM required_channels"
            )

            channels = cursor.fetchall()

            conn.close()

            if not channels:

                await message.reply(
                    "هیچ کانالی وجود ندارد.",
                    components=required_admin_menu()
                )

                return

            result = (
                "🗑️ برای حذف کانال، "
                "شماره آن را بفرست.\n\n"
            )

            for index, channel in enumerate(channels, 1):

                result += (
                    f"{index}. {channel['title']}\n"
                )

            user_states[user.user_id] = {
                "state": "required_delete",
                "channels": [dict(c) for c in channels]
            }

            await message.reply(result)

            return

        # -------------------------------------------------
        # حذف عضویت اجباری با شماره
        # -------------------------------------------------

        if isinstance(state, dict) and state.get("state") == "required_delete":

            try:

                index = int(text)

                channels = state["channels"]

                if index < 1 or index > len(channels):
                    raise ValueError

                channel_id = channels[index - 1]["id"]

            except ValueError:

                await message.reply(
                    "❌ شماره درست نیست."
                )

                return

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM required_channels WHERE id = ?",
                (channel_id,)
            )

            conn.commit()
            conn.close()

            user_states.pop(
                user.user_id,
                None
            )

            await message.reply(
                "✅ کانال حذف شد.",
                components=required_admin_menu()
            )

            return

        # -------------------------------------------------
        # کانال‌های کسب سکه
        # -------------------------------------------------

        if text == "📣 کانال‌های کسب سکه":

            await message.reply(
                "📣 مدیریت کانال‌های کسب سکه",
                components=earning_admin_menu()
            )

            return

        if text == "➕ افزودن کانال کسب سکه":

            user_states[user.user_id] = "earning_add"

            await message.reply(
                "➕ کانال کسب سکه\n\n"
                "لینک یا آیدی کانال رو بفرست.\n\n"
                "هر کاربر با عضویت در این کانال "
                "۱ سکه دریافت می‌کند."
            )

            return

        if text == "📋 لیست کانال‌های کسب سکه":

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT *
                FROM earning_channels
                WHERE active = 1
            """)

            channels = cursor.fetchall()

            conn.close()

            if not channels:

                await message.reply(
                    "📋 هنوز کانال کسب سکه‌ای وجود ندارد.",
                    components=earning_admin_menu()
                )

                return

            result = "📋 کانال‌های کسب سکه:\n\n"

            for index, channel in enumerate(channels, 1):

                result += (
                    f"{index}. {channel['title']}\n"
                    f"🪙 پاداش: {channel['reward']} سکه\n"
                    f"🔗 {channel['link']}\n\n"
                )

            await message.reply(
                result,
                components=earning_admin_menu()
            )

            return

        if text == "🗑️ حذف کانال کسب سکه":

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT *
                FROM earning_channels
                WHERE active = 1
            """)

            channels = cursor.fetchall()

            conn.close()

            if not channels:

                await message.reply(
                    "هیچ کانالی برای حذف وجود ندارد.",
                    components=earning_admin_menu()
                )

                return

            user_states[user.user_id] = {
                "state": "earning_delete",
                "channels": [dict(c) for c in channels]
            }

            result = (
                "🗑️ شماره کانالی که می‌خوای حذف کنی رو بفرست:\n\n"
            )

            for index, channel in enumerate(channels, 1):

                result += (
                    f"{index}. {channel['title']}\n"
                )

            await message.reply(result)

            return

        if isinstance(state, dict) and state.get("state") == "earning_delete":

            try:

                index = int(text)

                channels = state["channels"]

                if index < 1 or index > len(channels):
                    raise ValueError

                channel_id = channels[index - 1]["id"]

            except ValueError:

                await message.reply(
                    "❌ شماره درست نیست."
                )

                return

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM earning_channels WHERE id = ?",
                (channel_id,)
            )

            conn.commit()
            conn.close()

            user_states.pop(
                user.user_id,
                None
            )

            await message.reply(
                "✅ کانال کسب سکه حذف شد.",
                components=earning_admin_menu()
            )

            return

        # -------------------------------------------------
        # مدیریت سکه
        # -------------------------------------------------

        if text == "🪙 مدیریت سکه":

            await message.reply(
                "🪙 مدیریت سکه\n\n"
                "💰 هر سکه = ۲۰۰ تومان\n"
                "🔹 حداقل خرید = ۱۰۰ سکه\n"
                "🔹 حداکثر خرید = ۵۰۰ سکه\n"
                "🎁 سکه روزانه = ۵\n"
                "📢 عضویت در کانال کسب سکه = ۱ سکه\n"
                "👥 هر ممبر سفارش = ۲ سکه",
                components=admin_menu()
            )

            return

        # -------------------------------------------------
        # مدیریت هدیه
        # -------------------------------------------------

        if text == "🎁 مدیریت کد هدیه":

            await message.reply(
                "🎁 مدیریت کدهای هدیه",
                components=gift_admin_menu()
            )

            return

        if text == "➕ ساخت کد هدیه":

            user_states[user.user_id] = "gift_add"

            await message.reply(
                "➕ ساخت کد هدیه\n\n"
                "فرمت:\n\n"
                "BLUMIE20 20 50\n\n"
                "یعنی:\n"
                "🎟️ کد = BLUMIE20\n"
                "🪙 سکه = 20\n"
                "👥 ظرفیت = 50"
            )

            return

        if text == "📋 لیست کدهای هدیه":

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT *
                FROM gift_codes
                ORDER BY id DESC
            """)

            gifts = cursor.fetchall()

            conn.close()

            if not gifts:

                await message.reply(
                    "🎁 هیچ کد هدیه‌ای ساخته نشده.",
                    components=gift_admin_menu()
                )

                return

            result = "🎁 کدهای هدیه:\n\n"

            for gift in gifts:

                status = (
                    "🟢 فعال"
                    if gift["active"]
                    else "🔴 غیرفعال"
                )

                result += (
                    f"🎟️ {gift['code']}\n"
                    f"🪙 {gift['coins']} سکه\n"
                    f"👥 {gift['used_users']}/{gift['max_users']}\n"
                    f"{status}\n\n"
                )

            await message.reply(
                result,
                components=gift_admin_menu()
            )

            return

        # -------------------------------------------------
        # سفارش‌ها
        # -------------------------------------------------

        if text == "👥 سفارش‌ها":

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT *
                FROM orders
                ORDER BY id DESC
                LIMIT 30
            """)

            orders = cursor.fetchall()

            conn.close()

            if not orders:

                await message.reply(
                    "👥 هنوز سفارشی ثبت نشده.",
                    components=admin_menu()
                )

                return

            result = "👥 آخرین سفارش‌ها:\n\n"

            for order in orders:

                result += (
                    f"🆔 سفارش #{order['id']}\n"
                    f"👤 کاربر: {order['user_id']}\n"
                    f"📢 کانال: {order['channel_title']}\n"
                    f"👥 ممبر: {order['members']}\n"
                    f"🪙 سکه: {order['coins']}\n"
                    f"📌 وضعیت: {order['status']}\n\n"
                )

            await message.reply(
                result,
                components=admin_menu()
            )

            return

        # -------------------------------------------------
        # کاربران
        # -------------------------------------------------

        if text == "👤 کاربران":

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) AS count FROM users"
            )

            users = cursor.fetchone()["count"]

            conn.close()

            await message.reply(
                "👤 کاربران بلومی\n\n"
                f"👥 تعداد کاربران: {users}",
                components=admin_menu()
            )

            return

        # -------------------------------------------------
        # آمار
        # -------------------------------------------------

        if text == "📊 آمار":

            conn = get_db()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) AS count FROM users"
            )
            users = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) AS count FROM required_channels"
            )
            required = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) AS count FROM earning_channels WHERE active = 1"
            )
            earning = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT COUNT(*) AS count FROM orders"
            )
            orders = cursor.fetchone()["count"]

            cursor.execute("""
                SELECT COALESCE(SUM(coins), 0) AS total
                FROM users
            """)

            coins = cursor.fetchone()["total"]

            conn.close()

            await message.reply(
                "📊 آمار بلومی\n\n"
                f"👥 کاربران: {users}\n"
                f"🔒 عضویت اجباری: {required}\n"
                f"📣 کانال‌های کسب سکه: {earning}\n"
                f"👥 سفارش‌ها: {orders}\n"
                f"🪙 مجموع سکه کاربران: {coins}",
                components=admin_menu()
            )

            return

        # -------------------------------------------------
        # بازگشت به پنل مدیریت
        # -------------------------------------------------

        if text == "🔙 پنل مدیریت":

            user_states.pop(
                user.user_id,
                None
            )

            await message.reply(
                "👑 پنل مدیریت",
                components=admin_menu()
            )

            return

        # -------------------------------------------------
        # بازگشت به منوی اصلی
        # -------------------------------------------------

        if text == "🔙 منوی اصلی":

            user_states.pop(
                user.user_id,
                None
            )

            await message.reply(
                "🌸 منوی اصلی بلومی",
                components=main_menu()
            )

            return

    # =====================================================
    # سکه روزانه
    # =====================================================
    # این بخش را عمداً با یک دکمه جدا نکردیم.
    # چون جمع‌آوری سکه باید از کانال‌ها انجام شود.
    # =====================================================


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
