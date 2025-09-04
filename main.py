# -*- coding: utf-8 -*-
"""
КОЛОВРАТ — квест-бот с боёвкой, прокачкой и инвентарём.
Запуск на Render как Web Service (aiohttp слушает порт), а бот работает через long polling.

Нужно задать переменные окружения:
  BOT_TOKEN=<твой токен от BotFather>
  PORT=10000  (можно не задавать: Render сам положит PORT, но лучше зафиксировать)
"""

import os
import random
import asyncio
import logging
from typing import Dict, Any, Optional

from aiohttp import web
from aiogram import Bot, Dispatcher, types

# =========================
# БАЗОВЫЕ НАСТРОЙКИ
# =========================
logging.basicConfig(level=logging.INFO)
API_TOKEN = os.getenv("BOT_TOKEN")
if not API_TOKEN:
    raise RuntimeError("Не указан BOT_TOKEN")

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# =========================
# ИГРОВАЯ МОДЕЛЬ (in-memory)
# =========================

# Состояние игроков (простая in-memory-«БД»)
PLAYERS: Dict[int, Dict[str, Any]] = {}

# Небольшая подборка картинок (можете заменить на любые свои)
IMG = {
    "intro": "https://images.unsplash.com/photo-1455659817273-f96807779a8d?q=80&w=1200&auto=format&fit=crop",
    "forest": "https://images.unsplash.com/photo-1500382017468-9049fed747ef?q=80&w=1200&auto=format&fit=crop",
    "village": "https://images.unsplash.com/photo-1544735716-392fe2489ffa?q=80&w=1200&auto=format&fit=crop",
    "swamp": "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?q=80&w=1200&auto=format&fit=crop",
    "stones": "https://images.unsplash.com/photo-1519681393784-d120267933ba?q=80&w=1200&auto=format&fit=crop",
    "cave": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?q=80&w=1200&auto=format&fit=crop",
    "altar": "https://images.unsplash.com/photo-1519681393786-d9d86d1a017d?q=80&w=1200&auto=format&fit=crop",
    "battle": "https://images.unsplash.com/photo-1558980664-10eb5f3f83aa?q=80&w=1200&auto=format&fit=crop",
}

# Враги (примерный набор; в разных локациях будут разные)
ENEMIES = {
    "leshiy":   {"name": "Леший",     "hp": 60,  "atk": (7, 12),  "def": 2, "img": IMG["forest"],  "exp": 25, "gold": 7},
    "volkodlak":{"name": "Волкодлак", "hp": 85,  "atk": (9, 15),  "def": 3, "img": IMG["swamp"],   "exp": 40, "gold": 12},
    "moroznica":{"name": "Морозница", "hp": 100, "atk": (10, 16), "def": 4, "img": IMG["stones"],  "exp": 55, "gold": 18},
    "shade":    {"name": "Тень алтаря","hp": 140, "atk": (12, 19), "def": 5, "img": IMG["altar"],   "exp": 90, "gold": 30},
}

# 20 локаций (ветвящийся путь; для примера — компактная схема)
# В каждой сцене можно задать:
# - text         — описание
# - img          — картинка
# - choices      — кнопки переходов [{"label","to"}]
# - battle       — ключ врага из ENEMIES (если есть — сцена боёвки)
# - hint         — подсказка по запросу
SCENES: Dict[str, Dict[str, Any]] = {
    "start": {
        "text": (
            "<b>Коловрат — ведьмак Древней Руси.</b>\n\n"
            "Его призвали в северный уезд: ночью в лесу шепчут огоньки, "
            "в деревне пропадают люди, на болоте воет Волкодлак, "
            "а в каменных кругах стынет Морозница.\n\n"
            "Коловоротный амулет старцев укажет путь к алтарю — там скрыта причина беды.\n\n"
            "Готов начать путь?"
        ),
        "img": IMG["intro"],
        "choices": [
            {"label": "В путь ➜ Лесная тропа", "to": "forest_path"},
            {"label": "Осмотреть деревню", "to": "village"},
        ],
        "hint": "Начни с лесной тропы — там амулет поведёт дальше.",
    },
    "forest_path": {
        "text": (
            "Ты входишь в древний еловый бор. Тишина звенит, а между стволами пляшут огни.\n"
            "Амулет тёплый, путь верен."
        ),
        "img": IMG["forest"],
        "choices": [
            {"label": "Следовать огонькам", "to": "fireflies"},
            {"label": "Свернуть к болотцу", "to": "swamp_enter"},
        ],
        "hint": "Огоньки — не всегда обман. Но к болоту тоже придётся вернуться.",
    },
    "fireflies": {
        "text": "Огоньки выводят к огромному пню — и из тени выходит Леший...",
        "img": IMG["forest"],
        "battle": "leshiy",
        "choices": [{"label": "Дальше по следу", "to": "stone_circles"}],
        "hint": "Леший силён, но зелье или блок помогут пережить его удар.",
    },
    "swamp_enter": {
        "text": "Запах тины и шёпот тростника. Вдали слышится тяжёлое дыхание.",
        "img": IMG["swamp"],
        "choices": [
            {"label": "Идти к голосу", "to": "volkodlak_battle"},
            {"label": "Вернуться в лес", "to": "forest_path"},
        ],
        "hint": "Волкодлак хранит ключ к кругам камней.",
    },
    "volkodlak_battle": {
        "text": "Из камышей выходит Волкодлак. Его пасть блеснула клыками...",
        "img": IMG["swamp"],
        "battle": "volkodlak",
        "choices": [{"label": "Круги камней", "to": "stone_circles"}],
        "hint": "Учитывай защиту врага. Блок уменьшает урон.",
    },
    "stone_circles": {
        "text": (
            "Старые каменные круги. Лёд по ним растёт даже летом. "
            "Шепот уводит в глубину и зовёт по знакам..."
        ),
        "img": IMG["stones"],
        "choices": [
            {"label": "Отгадать руны", "to": "rune_puzzle"},
            {"label": "Пойти к пещерам", "to": "cave_1"},
        ],
        "hint": "Руны подскажут, где алтарь. Но можно и так дойти — длинной тропой.",
    },
    "rune_puzzle": {
        "text": "Руны вырастают морозом. Выбирай знак — круг раскроет путь.",
        "img": IMG["stones"],
        "choices": [
            {"label": "Знак Солнца (верно)", "to": "cave_1"},
            {"label": "Знак Ветра (дольше)", "to": "forest_deeper"},
        ],
        "hint": "Солнце — сердце коловорота.",
    },
    "forest_deeper": {
        "text": "Ты заблудился и кружил по чаще, но в конце концов вышел к утёсам.",
        "img": IMG["forest"],
        "choices": [{"label": "Войти в пещеры", "to": "cave_1"}],
    },
    "cave_1": {
        "text": "Сырой воздух пещер. Стены звенят от холода. В глубине кто-то шуршит.",
        "img": IMG["cave"],
        "choices": [
            {"label": "Дальше вглубь", "to": "cave_2"},
            {"label": "Вернуться к кругам", "to": "stone_circles"},
        ],
    },
    "cave_2": {
        "text": "На каменном карнизе лёд срастается в фигуры. Перед тобой Морозница...",
        "img": IMG["stones"],
        "battle": "moroznica",
        "choices": [{"label": "Тропа к алтарю", "to": "altar_path"}],
        "hint": "Если тяжело — используй зелье. После боя можно подлечиться ещё одним.",
    },
    "altar_path": {
        "text": "Из пещер тропа ведёт к святилищу. Амулет сияет жарче.",
        "img": IMG["altar"],
        "choices": [{"label": "К алтарю", "to": "altar_boss"}],
    },
    "altar_boss": {
        "text": "Небо тёмное, камни — как кости. На алтаре клубится тень...",
        "img": IMG["altar"],
        "battle": "shade",
        "choices": [{"label": "Завершить круг", "to": "final"}],
        "hint": "Тень сильна, но броня и верный удар решают.",
    },
    "final": {
        "text": (
            "<b>Круг завершён.</b> Амулет раскалился белым огнём, тень рассыпалась инеем.\n\n"
            "Зло пало. Люди вернутся к очагам, а лес стихнет.\n\n"
            "<i>Спасибо за игру!</i>"
        ),
        "img": IMG["intro"],
        "choices": [{"label": "Начать заново", "to": "start"}],
    },
}

# =========================
# УТИЛИТЫ И БОЙ
# =========================

def default_player() -> Dict[str, Any]:
    return {
        "scene": "start",
        "lvl": 1,
        "exp": 0,
        "exp_to_lvl": 50,
        "gold": 0,
        "atk": 10,       # базовый урон
        "def": 2,        # базовая защита
        "max_hp": 60,
        "hp": 60,
        "potions": 2,
        "items": set(),  # амулеты/ключи
        "mode": "story", # "story" или "battle"
        "enemy": None,   # активный враг
    }

def xp_gain(pl: Dict[str, Any], amount: int) -> str:
    pl["exp"] += amount
    text = f"✨ Получено опыта: <b>{amount}</b>."
    while pl["exp"] >= pl["exp_to_lvl"]:
        pl["exp"] -= pl["exp_to_lvl"]
        pl["lvl"] += 1
        pl["exp_to_lvl"] = int(pl["exp_to_lvl"] * 1.3)
        pl["max_hp"] += 10
        pl["atk"] += 2
        pl["def"] += 1
        pl["hp"] = min(pl["hp"] + 15, pl["max_hp"])
        text += (
            f"\n\n<b>Новый уровень {pl['lvl']}!</b>\n"
            f"+10 к здоровью, +2 к урону, +1 к защите. Немного подлечился."
        )
    return text

def enemy_copy(key: str) -> Dict[str, Any]:
    e = ENEMIES[key].copy()
    e["cur_hp"] = e["hp"]
    return e

def hp_bar(cur: int, m: int, width: int = 16) -> str:
    cur = max(0, min(cur, m))
    filled = int((cur / m) * width)
    return "█" * filled + "░" * (width - filled)

def player_panel(pl: Dict[str, Any]) -> str:
    return (
        f"🎚 Уровень: <b>{pl['lvl']}</b>  "
        f"⚔ Урон: <b>{pl['atk']}</b>  🛡 Защита: <b>{pl['def']}</b>\n"
        f"❤️ HP: <b>{pl['hp']}/{pl['max_hp']}</b> [{hp_bar(pl['hp'], pl['max_hp'])}]\n"
        f"🧪 Зелья: <b>{pl['potions']}</b>  🪙 Золото: <b>{pl['gold']}</b>\n"
    )

def battle_keyboard() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=3)
    kb.add(
        types.InlineKeyboardButton("Удар", callback_data="battle:hit"),
        types.InlineKeyboardButton("Блок", callback_data="battle:block"),
        types.InlineKeyboardButton("Выпить зелье", callback_data="battle:potion"),
    )
    kb.add(types.InlineKeyboardButton("Подсказка", callback_data="battle:hint"))
    return kb

def story_keyboard(scene_id: str) -> types.InlineKeyboardMarkup:
    scene = SCENES[scene_id]
    kb = types.InlineKeyboardMarkup(row_width=1)
    for ch in scene.get("choices", []):
        kb.add(types.InlineKeyboardButton(ch["label"], callback_data=f"go:{ch['to']}"))
    if scene.get("hint"):
        kb.add(types.InlineKeyboardButton("Подсказка", callback_data=f"hint:{scene_id}"))
    kb.add(types.InlineKeyboardButton("Инвентарь / Статус", callback_data="ui:status"))
    return kb

async def start_battle(user_id: int, enemy_key: str):
    pl = PLAYERS[user_id]
    pl["mode"] = "battle"
    pl["enemy"] = enemy_copy(enemy_key)

async def end_battle(user_id: int, win: bool) -> str:
    pl = PLAYERS[user_id]
    e = pl.get("enemy")
    pl["mode"] = "story"
    pl["enemy"] = None
    if not e:
        return ""
    if win:
        pl["gold"] += e["gold"]
        text = (
            f"🏆 Победа над <b>{e['name']}</b>!\n"
            f"🪙 Золото: +{e['gold']}.\n"
        )
        text += xp_gain(pl, e["exp"])
        return text
    else:
        # Проигрыш: откат немного HP и назад к локации
        pl["hp"] = max(10, int(pl["max_hp"] * 0.5))
        return "💀 Ты пал в бою. Очнулся у кромки леса, собравшись с силами..."

def enemy_panel(e: Dict[str, Any]) -> str:
    return f"<b>{e['name']}</b>\nHP: <b>{e['cur_hp']}/{e['hp']}</b> [{hp_bar(e['cur_hp'], e['hp'])}]"

def roll(atk_range):
    return random.randint(atk_range[0], atk_range[1])

# =========================
# ПОДАЧА СЦЕН И БОЙ
# =========================

async def send_scene(user_id: int, scene_id: str, edit: Optional[types.Message] = None):
    pl = PLAYERS[user_id]
    pl["scene"] = scene_id
    scene = SCENES[scene_id]

    # Если это сцена с боем — подготовить врага и показать панель боя
    if "battle" in scene and scene["battle"]:
        await start_battle(user_id, scene["battle"])
        e = PLAYERS[user_id]["enemy"]
        caption = (
            f"{scene['text']}\n\n"
            f"{player_panel(pl)}"
            f"---\n"
            f"{enemy_panel(e)}"
        )
        kb = battle_keyboard()
        if edit:
            await edit.edit_media(
                types.InputMediaPhoto(scene["img"], caption=caption),
                reply_markup=kb,
            )
        else:
            await bot.send_photo(user_id, scene["img"], caption=caption, reply_markup=kb)
        return

    # Обычная «сюжетная» сцена
    caption = f"{scene['text']}\n\n{player_panel(pl)}"
    kb = story_keyboard(scene_id)
    if edit:
        await edit.edit_media(
            types.InputMediaPhoto(scene["img"], caption=caption),
            reply_markup=kb,
        )
    else:
        await bot.send_photo(user_id, scene["img"], caption=caption, reply_markup=kb)

async def process_battle_turn(call: types.CallbackQuery, action: str):
    uid = call.from_user.id
    pl = PLAYERS[uid]
    e = pl["enemy"]

    if pl["mode"] != "battle" or not e:
        await call.answer("Сражение уже завершено.")
        return

    log = []

    # Ход игрока
    if action == "hit":
        dmg = max(0, pl["atk"] + random.randint(-3, 3) - e["def"])
        if dmg == 0:
            log.append("Ты ударил, но враг парировал урон.")
        else:
            e["cur_hp"] -= dmg
            log.append(f"⚔ Ты нанес {dmg} урона.")
    elif action == "block":
        log.append("🛡 Ты приготовился к блоку. Урон по тебе будет меньше.")
    elif action == "potion":
        if pl["potions"] > 0:
            heal = random.randint(20, 35)
            pl["potions"] -= 1
            pl["hp"] = min(pl["hp"] + heal, pl["max_hp"])
            log.append(f"🧪 Зелье восстановило {heal} HP.")
        else:
            await call.answer("Зелий не осталось!", show_alert=True)
    elif action == "hint":
        await call.answer("Удар — основной способ побеждать. Блок сильно режет входящий урон. Зелья — на крайний случай.")
        return

    # Проверка на победу
    if e["cur_hp"] <= 0:
        reward = await end_battle(uid, True)
        # после победы — показать одну кнопку «Дальше»
        scene = SCENES[pl["scene"]]
        next_to = scene.get("choices", [{"to": "start", "label": "Назад"}])[0]["to"]
        kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("Дальше →", callback_data=f"go:{next_to}")
        )
        caption = f"⚔ {e['name']} повержен!\n\n{reward}\n\n{player_panel(pl)}"
        await call.message.edit_caption(caption=caption, reply_markup=kb)
        await call.answer()
        return

    # Ход врага
    enemy_dmg = max(0, roll(e["atk"]) - pl["def"])
    if action == "block":
        enemy_dmg = max(0, int(enemy_dmg * 0.4))  # блок режет урон

    if enemy_dmg == 0:
        log.append(f"{e['name']} промахивается!")
    else:
        pl["hp"] -= enemy_dmg
        log.append(f"🔥 {e['name']} наносит {enemy_dmg} урона.")

    # Проверка на поражение
    if pl["hp"] <= 0:
        result = await end_battle(uid, False)
        kb = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("К лесу", callback_data="go:forest_path")
        )
        await call.message.edit_caption(
            caption=f"Ты пал…\n\n{result}\n\n{player_panel(pl)}",
            reply_markup=kb,
        )
        await call.answer()
        return

    # Продолжаем бой — обновляем панель
    caption = (
        f"{SCENES[pl['scene']]['text']}\n\n"
        f"{player_panel(pl)}"
        f"---\n"
        f"{enemy_panel(e)}\n\n"
        f"<i>{' '.join(log)}</i>"
    )
    await call.message.edit_caption(caption=caption, reply_markup=battle_keyboard())
    await call.answer()

# =========================
# ХЭНДЛЕРЫ БОТА
# =========================

@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    # новая игра или продолжение
    if uid not in PLAYERS:
        PLAYERS[uid] = default_player()
    else:
        # мягкий сброс к началу, но с сохранением прокачки/инвентаря
        pl = PLAYERS[uid]
        pl["scene"] = "start"
        pl["mode"] = "story"
        pl["enemy"] = None
        pl["hp"] = max(pl["hp"], int(pl["max_hp"] * 0.7))

    await message.answer(
        "🪓 <b>Коловрат</b> пробуждается.\nНажми «<b>В путь ➜ Лесная тропа</b>» чтобы начать.",
    )
    await send_scene(uid, "start")

@dp.callback_query_handler(lambda c: c.data.startswith("go:"))
async def cb_go(call: types.CallbackQuery):
    uid = call.from_user.id
    to_scene = call.data.split(":", 1)[1]
    await send_scene(uid, to_scene, edit=call.message)
    await call.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("hint:"))
async def cb_hint(call: types.CallbackQuery):
    scene_id = call.data.split(":", 1)[1]
    hint = SCENES.get(scene_id, {}).get("hint", "Подсказка не предусмотрена.")
    await call.answer(hint, show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "ui:status")
async def cb_status(call: types.CallbackQuery):
    uid = call.from_user.id
    pl = PLAYERS[uid]
    await call.answer(
        f"Статус:\n"
        f"Уровень {pl['lvl']}, {pl['exp']}/{pl['exp_to_lvl']} XP\n"
        f"HP {pl['hp']}/{pl['max_hp']}, Урон {pl['atk']}, Защита {pl['def']}\n"
        f"Золото: {pl['gold']}, Зелий: {pl['potions']}",
        show_alert=True
    )

@dp.callback_query_handler(lambda c: c.data.startswith("battle:"))
async def cb_battle(call: types.CallbackQuery):
    action = call.data.split(":", 1)[1]
    await process_battle_turn(call, action)

# =========================
# AIOHTTP WEB (заглушка для Render)
# =========================

async def handle_root(_):
    return web.Response(text="KOLVRAT bot is running.")

async def on_startup_app(app):
    # Запустить поллинг бота в фоне
    async def run_polling():
        # В aiogram v2 у Dispatcher есть корутина start_polling
        await dp.start_polling()
    asyncio.get_event_loop().create_task(run_polling())

def make_app():
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.on_startup.append(on_startup_app)
    return app

# Локальный запуск / Render запуск
if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    web.run_app(make_app(), host="0.0.0.0", port=port)
