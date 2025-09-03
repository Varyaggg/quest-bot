import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("BOT_TOKEN not set")

bot = Bot(TOKEN, parse_mode="Markdown")
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("Добро пожаловать в квест! 🎭\n\nТы у входа в старую типографию. "
                         "Чтобы войти, ответь: кто создал гражданский шрифт?")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped.")
