import os
import random
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Update, Message, ReplyKeyboardMarkup, KeyboardButton

# ========= ENV =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "kolovrat123")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

# ========= BOT CORE =========
bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ========= IN-MEMORY STATE (Demo) =========
PLAYERS: Dict[int, Dict[str, Any]] = {}
BATTLES: Dict[int, Dict[str, Any]] = {}  # активные бои

# ========= HELPERS =========
def hearts(hp: int, max_hp: int, parts: int = 10) -> str:
    if max_hp <= 0:
        return "░" * parts
    filled = max(0, min(parts, round(parts * hp / max_hp)))
    return "█" * filled + "░" * (parts - filled)

def kb(rows: List[List[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=True
    )

def base_menu(options: List[str]) -> ReplyKeyboardMarkup:
    # Кнопки локации + системная полоса
    rows = []
    row = []
    for i, opt in enumerate(options, 1):
        row.append(opt)
        if i % 2 == 0:
            rows.append(row); row = []
    if row: rows.append(row)
    rows.append(["Инвентарь", "Прокачка"])
    rows.append(["Подсказка", "Сброс"])
    return kb(rows)

# ========= PLAYER =========
def new_player(user_id: int, name: str) -> Dict[str, Any]:
    p = {
        "name": name,
        "level": 1,
        "exp": 0, "exp_to_next": 60,
        "stat_points": 0,
        "max_hp": 60, "hp": 60,
        "dmg_min": 6, "dmg_max": 10,
        "defense": 1,
        "potions": 3,
        "inventory": ["Коловоротный амулет"],
        "loc": 0,  # индекс локации
        "visited": set([0])
    }
    PLAYERS[user_id] = p
    return p

def player_damage(p: Dict[str, Any]) -> int:
    return random.randint(p["dmg_min"], p["dmg_max"])

def add_exp_and_level(p: Dict[str, Any], amount: int) -> Optional[str]:
    p["exp"] += amount
    notes = []
    while p["exp"] >= p["exp_to_next"]:
        p["exp"] -= p["exp_to_next"]
        p["level"] += 1
        p["stat_points"] += 2
        p["exp_to_next"] = int(p["exp_to_next"] * 1.45)
        notes.append(f"Достигнут <b>{p['level']} уровень</b>! Получено +2 очка характеристик.")
    return "\n".join(notes) if notes else None

def apply_stat(p: Dict[str, Any], stat: str) -> str:
    if p["stat_points"] <= 0:
        return "Нет свободных очков."
    if stat == "Сила":
        p["dmg_min"] += 1; p["dmg_max"] += 2; p["stat_points"] -= 1
        return "Сила повышена: урон вырос."
    if stat == "Живучесть":
        p["max_hp"] += 10; p["hp"] = min(p["hp"] + 12, p["max_hp"]); p["stat_points"] -= 1
        return "Живучесть повышена: +макс. HP и подлечились."
    if stat == "Защита":
        p["defense"] += 1; p["stat_points"] -= 1
        return "Защита повышена: входящий урон меньше."
    return "Неизвестная характеристика."

# ========= ENEMIES =========
ENEMIES: Dict[str, Dict[str, Any]] = {
    "Огонёк":     {"hp": 24, "dmg_min": 3, "dmg_max": 5, "armor": 0, "exp": 20,
                   "img":"https://images.unsplash.com/photo-1523442832476-6051fc06b7ea?q=80&w=1200"},
    "Кикимора":   {"hp": 32, "dmg_min": 4, "dmg_max": 6, "armor": 0, "exp": 26,
                   "img":"https://images.unsplash.com/photo-1561484930-998b6a53f6f0?q=80&w=1200"},
    "Упырь":      {"hp": 36, "dmg_min": 5, "dmg_max": 7, "armor": 0, "exp": 30,
                   "img":"https://images.unsplash.com/photo-1508214751196-bcfd4ca60f91?q=80&w=1200"},
    "Русалка":    {"hp": 40, "dmg_min": 5, "dmg_max": 8, "armor": 0, "exp": 34,
                   "img":"https://images.unsplash.com/photo-1473181488821-2d23949a045a?q=80&w=1200"},
    "Страж круга":{"hp": 42, "dmg_min": 6, "dmg_max": 9, "armor": 1, "exp": 36,
                   "img":"https://images.unsplash.com/photo-1519681393784-d120267933ba?q=80&w=1200"},
    "Вурдалак":   {"hp": 44, "dmg_min": 6, "dmg_max":10, "armor": 0, "exp": 38,
                   "img":"https://images.unsplash.com/photo-1524666041070-9d87656c25bb?q=80&w=1200"},
    "Ветряной дух":{"hp": 46, "dmg_min": 6, "dmg_max":10, "armor": 0, "exp": 40,
                   "img":"https://images.unsplash.com/photo-1482192505345-5655af888cc4?q=80&w=1200"},
    "Водяной":    {"hp": 48, "dmg_min": 6, "dmg_max":11, "armor": 1, "exp": 42,
                   "img":"https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1200"},
    "Морозница":  {"hp": 58, "dmg_min": 7, "dmg_max":12, "armor": 1, "exp": 60,
                   "img":"https://images.unsplash.com/photo-1549880338-65ddcdfd017b?q=80&w=1200"},
    "Волкодлак":  {"hp": 70, "dmg_min": 8, "dmg_max":13, "armor": 1, "exp": 90,
                   "img":"https://images.unsplash.com/photo-1518791841217-8f162f1e1131?q=80&w=1200"},
    "Тварь тени": {"hp": 62, "dmg_min": 7, "dmg_max":12, "armor": 1, "exp": 70,
                   "img":"https://images.unsplash.com/photo-1488521787991-ed7bbaae773c?q=80&w=1200"},
    "Корень Тьмы":{"hp": 85, "dmg_min": 9, "dmg_max":15, "armor": 2, "exp": 140,
                   "img":"https://images.unsplash.com/photo-1519682337058-a94d519337bc?q=80&w=1200"},
}

# ========= ADVENTURE NODES (20) =========
# Каждый узел: title, text, img, hint, options: список действий-кнопок
# action может содержать:
#  - goto: индекс следующей локации
#  - battle: имя врага, after: индекс после победы
#  - heal: количество HP
#  - item: добавить предмет в инвентарь
#  - end: финал
LOC: List[Dict[str, Any]] = [
    { # 0
        "title": "Лесная кромка",
        "text": ("<b>Коловрат — ведьмак Древней Руси.</b>\n\n"
                 "Тебя призвали в северный уезд: огоньки шепчут в чаще, люди исчезают, "
                 "на болоте воет Волкодлак, а в каменных кругах стынет Морозница. "
                 "Коловоротный амулет теплится у груди и указывает путь к алтарю.\n\n"
                 "Перед тобой тропы: к огонькам или к старой избе."),
        "img": "https://images.unsplash.com/photo-1501785888041-af3ef285b470?q=80&w=1200",
        "hint": "Огоньки могут завести, но и подсказать дорогу, если их усмирить.",
        "options": [
            {"text": "Тропа к огонькам", "goto": 1},
            {"text": "Старая изба", "goto": 2},
        ],
    },
    { # 1
        "title": "Чаща с огоньками",
        "text": "Светлящиеся огни кружат вокруг тебя. Один врезается в плечо — это не шутки.",
        "img": "https://images.unsplash.com/photo-1469474968028-56623f02e42e?q=80&w=1200",
        "hint": "Огонёк слаб к огню и оглушению.",
        "options": [
            {"text": "Сразиться с огоньком", "battle": "Огонёк", "after": 3},
            {"text": "Вернуться к кромке леса", "goto": 0}
        ],
    },
    { # 2
        "title": "Старая изба",
        "text": "Пустая изба. На лавке — мешочек трав и фляга с горьким настоем.",
        "img": "https://images.unsplash.com/photo-1482192505345-5655af888cc4?q=80&w=1200",
        "hint": "Зелья пригодятся. Осмотри избу внимательнее.",
        "options": [
            {"text": "Взять травяное зелье", "item": "Зелье", "heal": 0, "goto": 4},
            {"text": "Спуститься в погреб", "goto": 4},
        ],
    },
    { # 3
        "title": "Курган у тропы",
        "text": "На кургане кто-то шевелится. Холод веет из-под дерна — <b>упырь</b>!",
        "img": "https://images.unsplash.com/photo-1469474968028-56623f02e42e?q=80&w=1200",
        "hint": "Упырь не любит резких ударов и огня.",
        "options": [
            {"text": "Сразиться с упырём", "battle": "Упырь", "after": 5},
            {"text": "Отойти тихо", "goto": 5}
        ],
    },
    { # 4
        "title": "Погреб под избой",
        "text": "Мокрый запах и вязкие следы. Злая <b>кикимора</b> рвётся из щелей.",
        "img": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?q=80&w=1200",
        "hint": "Аард может прервать её прыжок.",
        "options": [
            {"text": "Сразиться с кикиморой", "battle": "Кикимора", "after": 5},
            {"text": "Рвануть к лесной дороге", "goto": 5}
        ],
    },
    { # 5
        "title": "Развилка у каменных кругов",
        "text": "Дорога уводит к болоту и к зимнему оврагу. В воздухе чувствуются знаки.",
        "img": "https://images.unsplash.com/photo-1519681393784-d120267933ba?q=80&w=1200",
        "hint": "Руны огня и холода пригодятся у алтаря.",
        "options": [
            {"text": "К болотам", "goto": 6},
            {"text": "К зимнему оврагу", "goto": 7}
        ],
    },
    { # 6
        "title": "Туманное болото",
        "text": "Пелена тянется над водой. Песня зовёт из омутов — это <b>русалка</b>.",
        "img": "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?q=80&w=1200",
        "hint": "Держись огня и не подпускай близко.",
        "options": [
            {"text": "Сразиться с русалкой", "battle": "Русалка", "after": 8},
            {"text": "Обойти по кочкам", "goto": 8}
        ],
    },
    { # 7
        "title": "Зимний овраг",
        "text": "Воздух режет кожу. В снегу — руна <b>Холода</b>, вырезанная ножом.",
        "img": "https://images.unsplash.com/photo-1482192596544-9eb780fc7f66?q=80&w=1200",
        "hint": "Руны можно хранить как предметы.",
        "options": [
            {"text": "Поднять руну Холода", "item": "Руна Холода", "goto": 9},
            {"text": "Назад к кругам", "goto": 5}
        ],
    },
    { # 8
        "title": "Святилище огня",
        "text": "Тёплый камень с насечками. Ты находишь <b>Руну Огня</b>.",
        "img": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1200",
        "hint": "С руной Игни бьёт сильнее.",
        "options": [
            {"text": "Взять руну Огня", "item": "Руна Огня", "goto": 9},
            {"text": "Вернуться к развилке", "goto": 5}
        ],
    },
    { # 9
        "title": "Деревня у реки",
        "text": "Избы пусты, двери сорваны. В переулке прячется вонящее нечто.",
        "img": "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?q=80&w=1200",
        "hint": "Вурдалак плотнее упыря.",
        "options": [
            {"text": "Сразиться с вурдалаком", "battle": "Вурдалак", "after": 10},
            {"text": "Пройти мимо к пещере", "goto": 10}
        ],
    },
    { # 10
        "title": "Пещера ветра",
        "text": "Вихри поют в проёмах. Меж камней — <b>ветряной дух</b>.",
        "img": "https://images.unsplash.com/photo-1519681393784-d120267933ba?q=80&w=1200",
        "hint": "Оглушение Аард полезно.",
        "options": [
            {"text": "Сразиться с духом", "battle": "Ветряной дух", "after": 11},
            {"text": "Свернуть к излучине", "goto": 11}
        ],
    },
    { # 11
        "title": "Излучина реки",
        "text": "Старая переправа. Из глубины выходит <b>водяной</b>.",
        "img": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?q=80&w=1200",
        "hint": "Держи зелья наготове.",
        "options": [
            {"text": "Сразиться с водяным", "battle": "Водяной", "after": 12},
            {"text": "Отойти в рощу", "goto": 12}
        ],
    },
    { # 12
        "title": "Священная роща",
        "text": "Ты собираешь целебные травы (+зелье) и отдыхаешь (+10 HP).",
        "img": "https://images.unsplash.com/photo-1501785888041-af3ef285b470?q=80&w=1200",
        "hint": "Наберись сил перед кружением камней.",
        "options": [
            {"text": "Подлечиться", "heal": 10, "item": "Зелье", "goto": 13},
            {"text": "Дальше к часовне", "goto": 13}
        ],
    },
    { # 13
        "title": "Старая часовня",
        "text": ("На столе три таблички-ответа. Руна спрашивает: <i>«Что удержит пламя и "
                 "не даст льду сковать алтарь?»</i>"),
        "img": "https://images.unsplash.com/photo-1473181488821-2d23949a045a?q=80&w=1200",
        "hint": "Ищи равновесие стихий.",
        "options": [
            {"text": "Огонь и Холод вместе", "item": "Руна Равновесия", "goto": 14},
            {"text": "Только Огонь", "battle": "Страж круга", "after": 14},
            {"text": "Только Холод", "battle": "Страж круга", "after": 14},
        ],
    },
    { # 14
        "title": "Каменные круги",
        "text": "Снег хрустит. Над кругами кружит <b>Морозница</b>.",
        "img": "https://images.unsplash.com/photo-1549880338-65ddcdfd017b?q=80&w=1200",
        "hint": "Игни поможет, но не забывай про зелья.",
        "options": [
            {"text": "Сразиться с Морозницей", "battle": "Морозница", "after": 15},
            {"text": "Обойти камни", "goto": 15}
        ],
    },
    { # 15
        "title": "Курган князя",
        "text": "Серп луны. Из-под камня выламывается <b>Волкодлак</b>.",
        "img": "https://images.unsplash.com/photo-1519682337058-a94d519337bc?q=80&w=1200",
        "hint": "Аард может сбить прыжок, Игни — поджечь шерсть.",
        "options": [
            {"text": "Сразиться с Волкодлаком", "battle": "Волкодлак", "after": 16},
            {"text": "Отступить к подземельям", "goto": 16}
        ],
    },
    { # 16
        "title": "Подземелье алтаря",
        "text": "Тени шевелятся на стенах. Холодная <b>Тварь тени</b> заслоняет путь.",
        "img": "https://images.unsplash.com/photo-1488521787991-ed7bbaae773c?q=80&w=1200",
        "hint": "Последний рывок перед алтарём.",
        "options": [
            {"text": "Сразиться с тварью тени", "battle": "Тварь тени", "after": 17},
            {"text": "Проскользнуть к алтарю", "goto": 17}
        ],
    },
    { # 17
        "title": "Алтарь — сердце беды",
        "text": "Корни оплели камень. Вздымается <b>Корень Тьмы</b>.",
        "img": "https://images.unsplash.com/photo-1519682337058-a94d519337bc?q=80&w=1200",
        "hint": "Игни + Руны = мощь. Следи за перезарядками.",
        "options": [
            {"text": "Финальная битва", "battle": "Корень Тьмы", "after": 18},
            {"text": "Попробовать разрушить печати", "battle": "Страж круга", "after": 18}
        ],
    },
    { # 18
        "title": "Утро в уезде",
        "text": "Тьма спала. Люди возвращаются. Амулет остывает. Круг завершён.",
        "img": "https://images.unsplash.com/photo-1500839941678-aae14dbfae9b?q=80&w=1200",
        "hint": "Можно начать снова, сохранив прокачку.",
        "options": [
            {"text": "Начать заново у кромки леса", "goto": 0},
            {"text": "Осмотреть награды", "goto": 19}
        ],
    },
    { # 19
        "title": "Награды",
        "text": "Ты собираешь трофеи и записываешь предания уезда.",
        "img": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?q=80&w=1200",
        "hint": "Возвращайся в любой момент.",
        "options": [
            {"text": "Вернуться к началу", "goto": 0}
        ],
    },
]

# ========= BATTLE ENGINE =========
def clamp_incoming(dmg: int, defense: int) -> int:
    return max(1, dmg - defense)

def start_battle(uid: int, enemy_name: str, after_idx: int) -> Dict[str, Any]:
    p = PLAYERS[uid]
    e = ENEMIES[enemy_name].copy()
    b = {
        "name": enemy_name,
        "e": e,
        "cool": {"igni": 0, "aard": 0},
        "stun": 0,
        "after": after_idx,
        "turn": 1,
    }
    BATTLES[uid] = b
    return b

def tick_cool(c: Dict[str, int]):
    for k in c:
        c[k] = max(0, c[k] - 1)

def fight_kb() -> ReplyKeyboardMarkup:
    return kb([
        ["Удар", "Игни"],
        ["Аард", "Выпить зелье"],
        ["Показать амулет", "Подсказка"],
        ["Прокачка"]
    ])

async def render_battle(message: Message, p: Dict[str, Any], b: Dict[str, Any], extra: str = ""):
    e = b["e"]
    txt = []
    if extra: txt.append(extra)
    # HP полосы
    emax = ENEMIES[b["name"]]["hp"]
    txt.append(f"<b>{b['name']}</b>\nHP {e['hp']}/{emax}  {hearts(e['hp'], emax)}")
    txt.append(f"\nТвои жизни: {p['hp']}/{p['max_hp']}  {hearts(p['hp'], p['max_hp'])}")
    txt.append("\nНужна подсказка — нажми «Подсказка».")
    await message.answer_photo(photo=e["img"], caption="\n".join(txt), reply_markup=fight_kb())

async def end_victory(message: Message, uid: int, p: Dict[str, Any], b: Dict[str, Any]):
    e = b["e"]; base = ENEMIES[b["name"]]
    gained = base["exp"]
    note = [f"Победа над <b>{b['name']}</b>! Получено {gained} опыта."]
    # шанс дропа
    if random.random() < 0.4:
        p["potions"] += 1
        note.append("Нашёл <b>зелье</b> (+1).")
    # небольшой шанс предмета
    if random.random() < 0.3:
        item = random.choice(["Сухой мох", "Треснувшая руна", "Клык волкодлака", "Осколок льда"])
        p["inventory"].append(item)
        note.append(f"Подобран предмет: <b>{item}</b>.")
    lvl = add_exp_and_level(p, gained)
    if lvl: note.append(lvl)
    # переход
    after = b["after"]
    del BATTLES[uid]
    p["loc"] = after
    await message.answer("\n".join(note))
    await show_location(message, p)

async def hero_dead(message: Message, uid: int, p: Dict[str, Any]):
    # «страховка» амулета — поднять до 1 HP и вывести из боя
    p["hp"] = 1
    if uid in BATTLES: del BATTLES[uid]
    await message.answer("Тьма сковывает сознание… Но амулет разгорается и вытягивает тебя из мрака (1 HP).")
    await show_location(message, p)

# ========= ADVENTURE RENDER =========
async def show_location(message: Message, p: Dict[str, Any], extra: str = ""):
    node = LOC[p["loc"]]
    title = f"<b>{node['title']}</b>\n\n"
    text = (title + node["text"])
    if extra: text += ("\n\n" + extra)
    buttons = [opt["text"] for opt in node["options"]]
    await message.answer_photo(node["img"], caption=text, reply_markup=base_menu(buttons))
    p["visited"].add(p["loc"])

# ========= COMMANDS =========
@router.message(F.text == "/start")
async def cmd_start(message: Message):
    uid = message.from_user.id
    name = message.from_user.first_name or "странник"
    p = new_player(uid, name)
    await show_location(message, p)

@router.message(F.text == "/help")
async def cmd_help(message: Message):
    await message.answer(
        "Команды: /start — начать заново, /help — помощь, /reset — сброс прогресса.\n"
        "Игра кнопками. В бою доступны Удар/Игни/Аард/Зелье, вне боя — Инвентарь/Прокачка/Подсказка."
    )

@router.message(F.text == "/reset")
async def cmd_reset(message: Message):
    uid = message.from_user.id
    PLAYERS.pop(uid, None); BATTLES.pop(uid, None)
    await message.answer("Прогресс сброшен. Нажми /start.")

# ========= SYSTEM BUTTONS =========
@router.message(F.text == "Инвентарь")
async def m_inv(message: Message):
    uid = message.from_user.id
    p = PLAYERS.get(uid)
    if not p: await message.answer("Сначала /start"); return
    inv = ", ".join(p["inventory"]) if p["inventory"] else "пусто"
    await message.answer(
        f"<b>Инвентарь</b>\nПредметы: {inv}\nЗелий: {p['potions']}\n"
        f"HP: {p['hp']}/{p['max_hp']} ({hearts(p['hp'], p['max_hp'])})"
    )

@router.message(F.text == "Прокачка")
async def m_lvl(message: Message):
    uid = message.from_user.id
    p = PLAYERS.get(uid)
    if not p: await message.answer("Сначала /start"); return
    await message.answer(
        f"<b>Прокачка</b>\nУровень: {p['level']}  Опыт: {p['exp']}/{p['exp_to_next']}\n"
        f"Очков: {p['stat_points']}\n"
        f"Сила: {p['dmg_min']}-{p['dmg_max']}  |  Живучесть: {p['max_hp']} HP  |  Защита: {p['defense']}",
        reply_markup=kb([["Сила","Живучесть","Защита"],["Назад"]])
    )

@router.message(F.text.in_(("Сила","Живучесть","Защита")))
async def m_apply_stat(message: Message):
    uid = message.from_user.id
    p = PLAYERS.get(uid)
    if not p: await message.answer("Сначала /start"); return
    await message.answer(apply_stat(p, message.text))

@router.message(F.text == "Назад")
async def m_back(message: Message):
    uid = message.from_user.id
    p = PLAYERS.get(uid)
    if not p: await message.answer("Сначала /start"); return
    # показать либо бой, либо локацию
    if uid in BATTLES:
        await render_battle(message, p, BATTLES[uid])
    else:
        await show_location(message, p)

@router.message(F.text == "Сброс")
async def m_reset_btn(message: Message):
    await cmd_reset(message)

@router.message(F.text == "Подсказка")
async def m_hint(message: Message):
    uid = message.from_user.id
    p = PLAYERS.get(uid)
    if not p: await message.answer("Сначала /start"); return
    if uid in BATTLES:
        await message.answer("В бою: Игни наносит огонь (CD 3 хода), Аард с шансом 50% оглушит на 1 ход. "
                             "Зелья лечат +22 HP. Следи за перезарядкой.")
    else:
        hint = LOC[p["loc"]]["hint"]
        await message.answer(f"Подсказка: {hint}")

# ========= LOCATION OPTIONS HANDLER =========
@router.message()
async def any_text(message: Message):
    uid = message.from_user.id
    p = PLAYERS.get(uid)
    if not p:
        await message.answer("Нажми /start"); return

    # Если идёт бой, обрабатываем боевые кнопки
    if uid in BATTLES:
        await handle_battle_input(message, p)
        return

    # Иначе — выбор в локации
    node = LOC[p["loc"]]
    text = message.text.strip()

    # Найдём опцию по тексту
    opt = next((o for o in node["options"] if o["text"] == text), None)
    if not opt:
        await message.answer("Выбирай вариант кнопкой ниже.")
        return

    # Выполняем действие
    extra = []
    if "item" in opt:
        item = opt["item"]
        if item == "Зелье":
            p["potions"] += 1
            extra.append("Подобрано зелье (+1).")
        else:
            if item not in p["inventory"]:
                p["inventory"].append(item)
                extra.append(f"Получено: <b>{item}</b>.")
    if "heal" in opt:
        heal = int(opt["heal"])
        p["hp"] = min(p["hp"] + heal, p["max_hp"])
        extra.append(f"Восстановлено {heal} HP.")

    if "battle" in opt:
        b = start_battle(uid, opt["battle"], opt["after"])
        await render_battle(message, p, b, extra="\n".join(extra))
        return

    if "goto" in opt:
        p["loc"] = opt["goto"]
        await show_location(message, p, extra="\n".join(extra) if extra else "")
        return

    if "end" in opt:
        await message.answer("Круг завершён. Нажми /start для новой игры.")
        return

# ========= BATTLE INPUT =========
async def handle_battle_input(message: Message, p: Dict[str, Any]):
    uid = message.from_user.id
    b = BATTLES[uid]
    e = b["e"]; base = ENEMIES[b["name"]]

    txt = message.text
    if txt == "Удар":
        dmg = player_damage(p)
        dmg = max(1, dmg - e.get("armor", 0))
        e["hp"] -= dmg
        msg = [f"Ты ударил на {dmg}."]
    elif txt == "Игни":
        if b["cool"]["igni"] > 0:
            await message.answer(f"Игни на перезарядке: {b['cool']['igni']} ход(а).")
            return
        dmg = random.randint(10, 16)
        # руна огня усиливает
        if "Руна Огня" in p["inventory"]:
            dmg += 3
        e["hp"] -= dmg
        b["cool"]["igni"] = 3
        msg = [f"Игни обжигает врага на {dmg}!"]
    elif txt == "Аард":
        if b["cool"]["aard"] > 0:
            await message.answer(f"Аард на перезарядке: {b['cool']['aard']} ход(а).")
            return
        b["cool"]["aard"] = 3
        if random.random() < 0.5:
            b["stun"] = 1
            msg = ["Аард сработал — враг оглушён и пропустит ход!"]
        else:
            msg = ["Аард не подействовал."]
    elif txt == "Выпить зелье":
        if p["potions"] <= 0:
            await message.answer("Зелий не осталось.")
            return
        p["potions"] -= 1
        heal = 22
        p["hp"] = min(p["hp"] + heal, p["max_hp"])
        msg = [f"Выпито зелье: +{heal} HP. Осталось зелий: {p['potions']}"]
    elif txt == "Показать амулет":
        await message.answer("Коловоротный амулет вспыхивает — один раз спасёт от гибели (оставит 1 HP).")
        return
    elif txt in ("Инвентарь","Прокачка","Подсказка","Сброс","Назад"):
        # системные кнопки и так обрабатываются отдельно — просто игнор
        return
    else:
        await message.answer("Используй кнопки боя.")
        return

    # Победа?
    if e["hp"] <= 0:
        await end_victory(message, uid, p, b)
        return

    # Ход врага
    if b["stun"] > 0:
        b["stun"] = 0
        msg.append(f"{b['name']} оглушён и пропускает ход.")
    else:
        edmg = random.randint(base["dmg_min"], base["dmg_max"])
        # руна холода немного смягчает урон холодных врагов
        if "Руна Холода" in p["inventory"] and b["name"] in ("Морозница","Корень Тьмы"):
            edmg = max(1, edmg - 2)
        edmg = clamp_incoming(edmg, p["defense"])
        p["hp"] -= edmg
        msg.append(f"{b['name']} наносит {edmg} урона.")

    if p["hp"] <= 0:
        await hero_dead(message, uid, p)
        return

    tick_cool(b["cool"])
    b["turn"] += 1
    await render_battle(message, p, b, extra="\n".join(msg))

# ========= FASTAPI (webhook & health) =========
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def tg_webhook(req: Request):
    data = await req.json()
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
