import os
import threading

from flask import Flask
from bale import Bot, Message, CallbackQuery
from bale import InlineKeyboardMarkup, InlineKeyboardButton


# =========================
# Render
# =========================

app = Flask(__name__)


@app.route("/")
def home():
    return "🌸 Blumie Bot is running!"


def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# =========================
# Bot
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN تنظیم نشده است!")

# 👑 صاحب بات
ADMIN_ID = 652485302

bot = Bot(token=BOT_TOKEN)


# =========================
# Admin Panel
# =========================

def admin_panel():

    keyboard = InlineKeyboardMarkup()

    keyboard.add(
        InlineKeyboardButton(
            text="📢 عضویت اجباری",
            callback_data="admin_channels"
        ),
        InlineKeyboardButton(
            text="🪙 مدیریت سکه",
            callback_data="admin_coins"
        ),
        row=1
    )

    keyboard.add(
        InlineKeyboardButton(
            text="🎁 کدهای هدیه",
            callback_data="admin_gifts"
        ),
        InlineKeyboardButton(
            text="👥 سفارش‌ها",
            callback_data="admin_orders"
        ),
        row=2
    )

    keyboard.add(
        InlineKeyboardButton(
            text="👤 کاربران",
            callback_data="admin_users"
        ),
        InlineKeyboardButton(
            text="📊 آمار",
            callback_data="admin_stats"
        ),
        row=3
    )

    return keyboard


# =========================
# Messages
# =========================

@bot.event
async def on_message(message: Message):

    if not message.content:
        return

    text = message.content.strip()
    user = message.author

    # /id
    if text == "/id":

        await message.reply(
            f"🆔 User ID شما:\n\n{user.user_id}"
        )

        return

    # /start
    if text == "/start":

        await message.reply(
            "🌸✨ به بلومی خوش اومدی! ✨🌸"
        )

        return

    # /admin
    if text == "/admin":

        if user.user_id != ADMIN_ID:

            await message.reply(
                "⛔ شما اجازه دسترسی به پنل مدیریت را ندارید."
            )

            return

        await message.reply(
            "👑 پنل مدیریت بلومی\n\n"
            "گزینه موردنظر را انتخاب کن 👇",
            components=admin_panel()
        )

        return


# =========================
# Callback
# =========================

@bot.event
async def on_callback(callback: CallbackQuery):

    user = callback.from_user
    data = callback.data

    if not data:
        return

    # فقط صاحب بات
    if user.user_id != ADMIN_ID:

        await callback.message.reply(
            "⛔ دسترسی غیرمجاز."
        )

        return

    if data.startswith("admin_"):

        await callback.message.reply(
            "👑 پنل مدیریت",
            components=admin_panel()
        )


# =========================
# Run
# =========================

if __name__ == "__main__":

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    print("🌸 Blumie Bot is starting...")
    print(f"👑 Admin ID: {ADMIN_ID}")

    bot.run()
