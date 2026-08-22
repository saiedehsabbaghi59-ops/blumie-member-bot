import os
import threading

from flask import Flask
from bale import Bot, Message


# =========================
# تنظیمات Render
# =========================

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


# =========================
# تنظیمات بات بله
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN تنظیم نشده است!")


bot = Bot(token=BOT_TOKEN)


@bot.event
async def on_ready():
    print("🌸 Blumie Bot is ready!")


@bot.event
async def on_message(message: Message):

    if not message.content:
        return

    if message.content.strip() == "/start":

        await message.reply(
            "🌸 به ممبرگیر بلومی خوش اومدی!\n\n"
            "🪙 اینجا می‌تونی سکه جمع کنی، "
            "برای کانالت سفارش ثبت کنی و از امکانات بلومی استفاده کنی.\n\n"
            "✨ به بلومی خوش اومدی!"
        )


# =========================
# اجرای همزمان وب‌سرور و بات
# =========================

if __name__ == "__main__":

    web_thread = threading.Thread(
        target=run_web_server,
        daemon=True
    )

    web_thread.start()

    print("🌐 Render web server started!")

    bot.run()
