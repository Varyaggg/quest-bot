import os
import httpx
from fastapi import FastAPI, Request, HTTPException

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret123")

app = FastAPI()

async def handle_update(update: dict):
    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    if text.startswith("/start"):
        reply = ("Добро пожаловать в квест! 🎭\n\n"
                 "Ты у входа в старую типографию.\n"
                 "Вопрос 1: кто создал гражданский шрифт?")
    elif "петр" in text.lower() or "пётр" in text.lower():
        reply = ("Верно! Этап 2: расшифруй 26-15-20-1 (A=1).")
    elif text.strip().upper() == "ZOTA":
        reply = ("Отлично! Этап 3: Секрет успеха типографии в ____ печати.\n"
                 "Подсказка: C,M,Y,K печатают раздельно.")
    elif "поцвет" in text.lower():
        reply = ("Финал 🎉 Ты прошёл квест! Слово — оружие.")
    else:
        reply = ("Не понял. Попробуй /start или ответ на текущий этап.")

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(f"{TELEGRAM_API}/sendMessage",
                          json={"chat_id": chat_id, "text": reply})

@app.get("/")
def ok():
    return {"status": "ok"}

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def telegram_webhook(request: Request):
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")
    await handle_update(update)
    return {"ok": True}
