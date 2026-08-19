import os

from bale import Bot, Message

# دریافت اطلاعات محرمانه از تنظیمات Render
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN تنظیم نشده است!")

bot = Bot(token=BOT_TOKEN)


@bot.event
async def on_ready():
    print(f"🌸 {bot.user.username} is ready!")


@bot.event
async def on_message(message: Message):
    if message.content == "/start":
        await message.reply(
            "🌸 به ممبرگیر بلومی خوش اومدی!\n\n"
            "🪙 اینجا می‌تونی سکه جمع کنی، "
            "برای کانالت سفارش ثبت کنی و از امکانات بلومی استفاده کنی.\n\n"
            "✨ از منوی زیر شروع کن:"
        )


bot.run()
