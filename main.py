import os
import asyncio
import logging

from fastapi import FastAPI
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor

import uvicorn

# ------------ ЛОГИ ------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("quest-bot")

# ------------ НАСТРОЙКИ ------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN or len(BOT_TOKEN) < 30:
    # Прерываем запуск, чтобы в логах было ясно, что нет токена
    raise RuntimeError("Environment variable BOT_TOKEN is missing or invalid.")

PORT = int(os.getenv("PORT", "10000"))  # Render передаёт PORT

# ------------ HTTP-СЕРВЕР (для Render) ------------
app = FastAPI(title="QuestBot HTTP")

@app.get("/")
async def root():
    return {"ok": True, "app": "quest-bot", "status": "running"}

@app.get("/healthz")
async def health():
    return {"status": "healthy"}

# ------------ TELEGRAM-БОТ ------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    text = (
        "Привет! Я Коловрат — ведьмак Древней Руси.\n\n"
        "Это демо-бот: я жив, отвечаю и готов к приключениям.\n\n"
        "Команды:\n"
        "/help — помощь\n"
        "/ping — проверить отклик\n"
    )
    await message.answer(text)

@dp.message_handler(commands=["help"])
async def cmd_help(message: types.Message):
    await message.answer("Пока что тут демо. Но сервер и бот работают корректно ✅")

@dp.message_handler(commands=["ping"])
async def cmd_ping(message: types.Message):
    await message.answer("pong")

@dp.message_handler()
async def echo_fallback(message: types.Message):
    await message.answer("Я на связи. Используй /help или /ping 😉")

# ------------ ЗАПУСК ------------
async def run_bot():
    """
    Запускаем polling aiogram в этом же процессе.
    """
    log.info("Starting Telegram bot polling...")
    # skip_updates=True — на старте пропускаем старые апдейты
    executor.start_polling(dp, skip_updates=True)

async def run_http():
    """
    Поднимаем HTTP-сервер Uvicorn на порту, который даёт Render.
    """
    log.info(f"Starting HTTP server on 0.0.0.0:{PORT} ...")
    config = uvicorn.Config(app=app, host="0.0.0.0", port=PORT, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    """
    Параллельно запускаем и бота, и HTTP-сервер.
    """
    # Запускаем HTTP в отдельной таске, чтобы одновременно работал polling
    http_task = asyncio.create_task(run_http())

    # polling — блокирующий вызов (aiogram 2.x). Запустим его в отдельном потоке,
    # чтобы не блокировать ивент-луп, или просто в текущем потоке.
    # Надёжнее — выполнить в отдельном треде:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, run_bot)

    # Если polling завершится (обычно — только при падении), дожмём HTTP
    await http_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutting down...")
