import os
import json
import random
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI, Request, HTTPException

# === Настройки ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret123")
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE", "").rstrip("/")
TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI()

# === Утилиты ===
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", (s or "")).strip().lower()
    s = s.replace("ё", "е")
    return s

async def tg(method: str, payload: dict):
    async with httpx.AsyncClient(timeout=20) as cl:
        r = await cl.post(f"{TG}/{method}", json=payload)
        r.raise_for_status()
        return r.json()

def kb(rows):
    return {"inline_keyboard": [[{"text": b["text"], "callback_data": b["data"]} for b in row] for row in rows]}

def hp_bar(cur: int, mx: int, width: int = 10) -> str:
    cur = max(0, min(cur, mx))
    if mx <= 0:
        return "░" * width
    filled = int(round(width * cur / mx))
    filled = max(0, min(filled, width))
    return "█" * filled + "░" * (width - filled)

async def send_text(chat_id: int, text: str, markup: Optional[dict] = None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = markup
    await tg("sendMessage", payload)

async def send_photo(chat_id: int, url: str, caption: str, markup: Optional[dict] = None):
    payload = {"chat_id": chat_id, "photo": url, "caption": caption, "parse_mode": "Markdown"}
    if markup:
        payload["reply_markup"] = markup
    try:
        await tg("sendPhoto", payload)
    except Exception:
        await send_text(chat_id, caption, markup)

# === Модель состояния ===
@dataclass
class Combat:
    enemy: str
    max_hp: int
    hp: int
    img: str
    dmg_min: int
    dmg_max: int
    hint: str
    win_to: str
    trait: Optional[str] = None

@dataclass
class Session:
    # Прокачиваемый персонаж
    max_hp: int = 50
    hp: int = 50
    level: int = 1
    xp: int = 0  # задел для будущего опыта
    dmg_min: int = 4
    dmg_max: int = 8

    # Прочее состояние
    location: str = "intro"
    inventory: List[str] = field(default_factory=list)
    finished: bool = False
    combat: Optional[Combat] = None

SESS: Dict[int, Session] = {}

def sget(uid: int) -> Session:
    if uid not in SESS:
        SESS[uid] = Session()
    return SESS[uid]

def have(s: Session, item: str) -> bool:
    n = norm(item)
    return any(norm(x) == n for x in s.inventory)

def add_item(s: Session, item: str):
    if not have(s, item):
        s.inventory.append(item)

def heal(s: Session, amount: int):
    s.hp = min(s.max_hp, s.hp + amount)

def level_up(s: Session):
    # Повышение уровня: +1 уровень, +10 к макс. HP, полное восстановление HP,
    # небольшой рост урона
    s.level += 1
    s.max_hp += 10
    s.hp = s.max_hp
    s.dmg_min += 1
    s.dmg_max += 2

# === HTTP-хендлеры ===
@app.get("/")
def ok():
    return {"status": "ok"}

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def webhook(request: Request):
    try:
        upd = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    msg = upd.get("message")
    if msg and "text" in msg:
        chat_id = msg["chat"]["id"]
        text = norm(msg.get("text", ""))

        if text.startswith("/start"):
            SESS[chat_id] = Session()
            s = sget(chat_id)
            await send_text(
                chat_id,
                f"Начало игры. У тебя {s.hp}/{s.max_hp} HP. "
                f"Уровень: {s.level}. Урон: {s.dmg_min}-{s.dmg_max}."
            )
            return {"ok": True}

        if text in ("/жизни", "/hp"):
            s = sget(chat_id)
            await send_text(chat_id, f"❤ Жизни: {s.hp}/{s.max_hp}  [{hp_bar(s.hp, s.max_hp)}]")
            return {"ok": True}

        if text in ("/статы", "/stats"):
            s = sget(chat_id)
            inv = ", ".join(s.inventory) if s.inventory else "пусто"
            await send_text(
                chat_id,
                "📊 *Статы*\n"
                f"• Уровень: {s.level}\n"
                f"• HP: {s.hp}/{s.max_hp}\n"
                f"• Урон: {s.dmg_min}-{s.dmg_max}\n"
                f"• Инвентарь: {inv}"
            )
            return {"ok": True}

        if text in ("/сброс", "/reset"):
            SESS[chat_id] = Session()
            s = sget(chat_id)
            await send_text(chat_id, f"Прогресс сброшен. HP: {s.hp}/{s.max_hp}. Уровень: {s.level}.")
            return {"ok": True}

    cq = upd.get("callback_query")
    if cq:
        data = cq.get("data", "")
        chat_id = cq["message"]["chat"]["id"]
        await tg("answerCallbackQuery", {"callback_query_id": cq["id"]})
        s = sget(chat_id)

        if data == "fight:potion":
            if have(s, "зелье"):
                heal(s, 15)
                s.inventory = [x for x in s.inventory if norm(x) != "зелье"]
                await send_text(chat_id, f"🍵 Ты выпил зелье. HP: {s.hp}/{s.max_hp}")
            else:
                await send_text(chat_id, "Зелья нет.")
            return {"ok": True}

        if data == "fight:win":
            level_up(s)
            await send_text(
                chat_id,
                f"🏆 Победа! Новый уровень: {s.level}. "
                f"HP: {s.hp}/{s.max_hp}. Урон: {s.dmg_min}-{s.dmg_max}."
            )
            return {"ok": True}

    return {"ok": True}
