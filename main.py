import os
import httpx
import unicodedata
from fastapi import FastAPI, Request, HTTPException
from dataclasses import dataclass, field
from typing import List, Dict

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret123")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

app = FastAPI()

# --------- Вспомогалки ----------
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", (s or "")).strip().lower()
    s = s.replace("ё", "е")
    return s

async def tg(method: str, json: dict):
    async with httpx.AsyncClient(timeout=15) as cl:
        r = await cl.post(f"{TELEGRAM_API}/{method}", json=json)
        r.raise_for_status()
        return r.json()

async def say(chat_id: int, text: str):
    await tg("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"})

async def pic(chat_id: int, url: str, caption: str):
    # если картинка недоступна, всё равно пришлём текст
    try:
        await tg("sendPhoto", {"chat_id": chat_id, "photo": url, "caption": caption, "parse_mode": "Markdown"})
    except Exception:
        await say(chat_id, caption)

# --------- Сцены (картинки можно заменить своими URL) ----------
SCENE = {
    1:  {"img": "https://images.unsplash.com/photo-1501785888041-af3ef285b470", "caption": "🌲 *Комната 1 — Врата деревни*\nК северу тянет дорога и запах дыма. Напиши: *готов*."},
    2:  {"img": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee", "caption": "👣 *Комната 2 — Следы в грязи*\nСлед уводит в чащу. Куда идёшь? Напиши: *налево* или *направо*."},
    3:  {"img": "https://images.unsplash.com/photo-1617191519009-8f6a0c2e6c7f", "caption": "☀️ *Комната 3 — Руна Солнца*\n«То, что режет тьму». Одним словом: _..._"},
    4:  {"img": "https://images.unsplash.com/photo-1509043759401-136742328bb3", "caption": "🌿 *Комната 4 — Леший*\nШёпоты ветвей. Что применишь? *игни* или *огонь*."},
    5:  {"img": "https://images.unsplash.com/photo-1520256862855-398228c41684", "caption": "🌾 *Комната 5 — Травник*\nНайдены травы. Напиши *взять*, чтобы собрать их."},
    6:  {"img": "https://images.unsplash.com/photo-1556909190-97b8f3f2ab1b", "caption": "🧪 *Комната 6 — Варка зелья*\nСвари зелье. Напиши: *сварить*."},
    7:  {"img": "https://images.unsplash.com/photo-1504898770365-14faca6f86e1", "caption": "💨 *Комната 7 — Туманник*\nМерцающий силуэт. Что сделаешь? *выпить зелье* или *игни*."},
    8:  {"img": "https://images.unsplash.com/photo-1504196606672-aef5c9cefc92", "caption": "🧩 *Комната 8 — Загадка лука*\n«Сидит дед, во сто шуб одет». Ответ:"},
    9:  {"img": "https://images.unsplash.com/photo-1549880338-65ddcdfd017b", "caption": "🪬 *Комната 9 — Сокровищница*\nКоловоротный амулет на пьедестале. Напиши *взять*."},
    10: {"img": "https://images.unsplash.com/photo-1519681393784-d120267933ba", "caption": "❄️ *Комната 10 — Морозница*\nЛедяной дух холодит кровь. Покажи *амулет*."},
    11: {"img": "https://images.unsplash.com/photo-1519710164239-da123dc03ef4", "caption": "⚒️ *Комната 11 — Кузница*\nНа наковальне лежит слиток. Напиши *взять*, чтобы получить *серебряный клинок*."},
    12: {"img": "https://images.unsplash.com/photo-1482192505345-5655af888cc4", "caption": "🐺 *Комната 12 — Волколак*\nВоет у кургана. Чем добьёшь? Напиши: *серебро* или *клинок*."},
    13: {"img": "https://images.unsplash.com/photo-1500021802231-0a1ff452b1d1", "caption": "✂️ *Комната 13 — Загадка*\n«Два кольца, два конца, посредине гвоздик» — ответ:"},
    14: {"img": "https://images.unsplash.com/photo-1501785888041-af3ef285b470", "caption": "🔵 *Комната 14 — Болотные огоньки*\nМанят в трясину. Правильное действие: *вернуться*."},
    15: {"img": "https://images.unsplash.com/photo-1501785888041-af3ef285b470?ixid=fakel", "caption": "🔥 *Комната 15 — Пещера у входа*\nФакел у стены. Напиши *взять*."},
    16: {"img": "https://images.unsplash.com/photo-1454179083322-198bb4daae1b", "caption": "🌑 *Комната 16 — Сплошная тьма*\nЗажги путь: напиши *факел* или *зажечь*."},
    17: {"img": "https://images.unsplash.com/photo-1469474968028-56623f02e42e", "caption": "🐉 *Комната 17 — Змей под сводом*\nВоздух дрожит. Твой ход: *аард* или *ветер*."},
    18: {"img": "https://images.unsplash.com/photo-1494738073002-80e2b34f3f49", "caption": "🧠 *Комната 18 — Загадка времени*\n«Утром на четырёх, днём на двух, вечером на трёх». Ответ:"},
    19: {"img": "https://images.unsplash.com/photo-1482192505345-5655af888cc4?ixid=fakel", "caption": "⛨ *Комната 19 — Алтарь*\nСкажи слово, что завершает круг и защищает край: *коловрат*."},
    20: {"img": "https://images.unsplash.com/photo-1519681393784-d120267933ba?ixid=fakel", "caption": "🏁 *Комната 20 — Финал*\nЗло рассеяно. Ты получаешь трофей и славу. Напиши */start*, чтобы пройти снова."},
}

# --------- Состояние игрока (в памяти) ----------
@dataclass
class Session:
    hp: int = 5
    stage: int = 1
    inventory: List[str] = field(default_factory=list)
    finished: bool = False

SESS: Dict[int, Session] = {}

def sget(uid: int) -> Session:
    if uid not in SESS:
        SESS[uid] = Session()
    return SESS[uid]

async def show_stage(chat_id: int, stage: int):
    sc = SCENE[stage]
    await pic(chat_id, sc["img"], sc["caption"])

# --------- Правила уровней ----------
def has(inv: List[str], item: str) -> bool:
    return any(norm(x) == norm(item) for x in inv)

# Проверка ответа; возвращает (ok, hint, inventory_change)
def check(stage: int, t: str, inv: List[str]):
    t = norm(t)
    ok = False
    hint = None
    gain = None
    use = None

    if stage == 1:
        ok = (t == "готов")
        hint = "Напиши *готов*."
    elif stage == 2:
        ok = (t == "налево")
        hint = "След уходит налево."
    elif stage == 3:
        ok = (t == "свет")
        hint = "То, что режет тьму."
    elif stage == 4:
        ok = t in ("игни", "огонь")
        hint = "Леший боится огня — *игни*."
    elif stage == 5:
        ok = t.startswith("взять")
        gain = "травы"
        hint = "Напиши *взять*."
    elif stage == 6:
        if has(inv, "травы"):
            ok = t.startswith("сварить")
            if ok: gain = "зелье"
            hint = "Если собрал травы — напиши *сварить*."
        else:
            ok = False
            hint = "Нет трав. Вернись мысленно: на предыдущем этапе было *взять* травы."
    elif stage == 7:
        ok = ("зелье" in t) or (t in ("игни",))
        use = "зелье" if "зелье" in t else None
        hint = "Можно *выпить зелье* или применить *игни*."
    elif stage == 8:
        ok = (t == "лук")
        hint = "Дед во сто шуб — это *лук*."
    elif stage == 9:
        ok = t.startswith("взять")
        gain = "амулет"
        hint = "Напиши *взять*."
    elif stage == 10:
        ok = "амулет" in t or has(inv, "амулет")
        hint = "Покажи *амулет*."
    elif stage == 11:
        ok = t.startswith("взять")
        gain = "серебряный клинок"
        hint = "Напиши *взять*."
    elif stage == 12:
        ok = ("серебро" in t) or ("клинок" in t) or ("серебряный" in t)
        hint = "Волколак боится *серебра*."
    elif stage == 13:
        ok = (t == "ножницы")
        hint = "Два кольца, два конца… — *ножницы*."
    elif stage == 14:
        ok = (t == "вернуться")
        hint = "Огоньки заманивают — лучше *вернуться*."
    elif stage == 15:
        ok = t.startswith("взять")
        gain = "факел"
        hint = "Напиши *взять*."
    elif stage == 16:
        ok = (t == "факел") or ("зажечь" in t)
        hint = "Зажги *факел*."
    elif stage == 17:
        ok = (t == "аард") or (t == "ветер")
        hint = "Подействует знак *Аард* (ветер)."
    elif stage == 18:
        ok = (t == "человек")
        hint = "Это *человек*."
    elif stage == 19:
        ok = (t == "коловрат")
        hint = "Скажи слово силы — *коловрат*."
    elif stage == 20:
        ok = True  # финал — просто повтор сцены
    return ok, hint, gain, use

# --------- FastAPI ----------
@app.get("/")
def ok():
    return {"status": "ok"}

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def webhook(request: Request):
    try:
        upd = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    msg = upd.get("message") or upd.get("edited_message")
    if not msg:
        return {"ok": True}
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    t = norm(text)

    # команды
    if t.startswith("/start"):
        SESS[chat_id] = Session()
        await pic(chat_id, SCENE[1]["img"],
                  "🛡 *Коловрат — ведьмак Древней Руси*\n"
                  "Северный уезд ждёт спасения. У тебя 5 жизней, инвентарь пуст.\n"
                  "Команды: /hp /inv /help /reset\n")
        await show_stage(chat_id, 1)
        return {"ok": True}

    if t == "/help":
        await say(chat_id, "Команды: /start — заново, /hp — жизни, /inv — инвентарь, /reset — сброс.\n"
                           "Пиши ответы одним словом или короткой фразой.")
        return {"ok": True}

    if t == "/hp":
        s = sget(chat_id)
        await say(chat_id, f"❤ Жизни: {s.hp} | Комната: {s.stage}/20")
        return {"ok": True}

    if t == "/inv":
        s = sget(chat_id)
        inv = ", ".join(s.inventory) if s.inventory else "пусто"
        await say(chat_id, f"🎒 Инвентарь: {inv}")
        return {"ok": True}

    if t == "/reset":
        SESS[chat_id] = Session()
        await say(chat_id, "Прогресс сброшен.")
        await show_stage(chat_id, 1)
        return {"ok": True}

    # игровая логика
    s = sget(chat_id)
    if s.finished:
        await say(chat_id, "Квест завершён! Напиши /start, чтобы начать заново.")
        return {"ok": True}

    ok, hint, gain, use = check(s.stage, t, s.inventory)

    if ok:
        # применение / получение предметов
        if use:
            # расходник — убираем
            s.inventory = [x for x in s.inventory if norm(x) != norm(use)]
        if gain:
            if not has(s.inventory, gain):
                s.inventory.append(gain)

        # переход вперёд
        if s.stage < 20:
            s.stage += 1
            await show_stage(chat_id, s.stage)
        else:
            s.finished = True
            await show_stage(chat_id, 20)
        return {"ok": True}

    # неверный ответ
    s.hp -= 1
    if s.hp <= 0:
        s.finished = True
        await say(chat_id, "💀 Жизни закончились. /start — начать заново.")
    else:
        await say(chat_id, f"Не то. Подсказка: {hint}\n❤ Осталось жизней: {s.hp}")
        # повтор текущей сцены (для удобства)
        await show_stage(chat_id, s.stage)

    return {"ok": True}
