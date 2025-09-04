
import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.utils.executor import start_webhook
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from game_data import SCENES, MONSTERS, ITEMS, BASE_PLAYER, rnd, clamp, safe_fight_plan, hp_bar

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE")  # e.g. https://your-service.onrender.com
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secretpath")
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = int(os.getenv("PORT", "10000"))

if not BOT_TOKEN:
    raise RuntimeError("Set BOT_TOKEN env var")

bot = Bot(BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# In-memory state (per user)
USERS = {}

def get_state(uid):
    if uid not in USERS:
        USERS[uid] = {
            "sceneId": "start",
            "player": dict(BASE_PLAYER),
            "bag": [],
            "runes": [],
            "combat": None
        }
    return USERS[uid]

def kb_choices(scene, state):
    kb = InlineKeyboardMarkup(row_width=2)
    if scene["type"] == "puzzle":
        for i, o in enumerate(scene["puzzle"]["opts"]):
            kb.insert(InlineKeyboardButton(o["t"], callback_data=f"p:{i}"))
        kb.add(InlineKeyboardButton("💡 Подсказка", callback_data="hint"))
        kb.add(InlineKeyboardButton("↩️ Назад", callback_data="to:start"))
    elif scene["type"] == "combat":
        kb.add(InlineKeyboardButton("⚔️ Атаковать", callback_data="act:hit"),
               InlineKeyboardButton("🛡 Парирование", callback_data="act:parry"))
        usable = [n for n in state["bag"] if n in ("лекарская трава","оберег от сглаза","жар-птицы перо")]
        for n in usable:
            kb.add(InlineKeyboardButton(f"🎒 {n}", callback_data=f"use:{n}"))
        kb.add(InlineKeyboardButton("💡 Подсказка", callback_data="hint"))
        kb.add(InlineKeyboardButton("↩️ Отступить", callback_data="to:map-choice"))
    else:
        for i, ch in enumerate(scene.get("choices", [])):
            if ch.get("to"):
                kb.insert(InlineKeyboardButton(ch["t"], callback_data=f"to:{ch['to']}"))
        kb.add(InlineKeyboardButton("💡 Подсказка", callback_data="hint"))
    return kb

async def enter_scene(uid, scene_id):
    s = get_state(uid)
    s["sceneId"] = scene_id
    scene = SCENES[scene_id]
    # onEnterGive
    for g in scene.get("onEnterGive", []):
        if ITEMS.get(g, {}).get("type") == "rune":
            if g not in s["runes"]:
                s["runes"].append(g)
        else:
            s["bag"].append(g)
    # init combat
    if scene["type"] == "combat":
        enemies = [{"kind": e["kind"], "hp": MONSTERS[e["kind"]]["baseHp"]} for e in scene["combat"]["enemies"]]
        # adaptive
        if s["player"]["hp"] < s["player"]["maxHp"]*0.35:
            for e in enemies: e["hp"] = int(e["hp"]*0.8)
        if safe_fight_plan(s["player"], enemies) == "tooHard":
            enemies[0]["hp"] = int(enemies[0]["hp"]*0.75)
            enemies = enemies[:max(1, len(enemies))]
        s["combat"] = {"enemies": enemies, "guard":0, "turn":"player", "sceneId": scene_id}
    else:
        s["combat"] = None
    return await render_scene(uid)

def fmt_state(uid):
    s = get_state(uid)
    p = s["player"]
    parts = [f"<b>Здоровье:</b> {p['hp']}/{p['maxHp']} {hp_bar(p['hp'], p['maxHp'])}",
             f"<b>Урон:</b> {p['atk'][0]}–{p['atk'][1]} • <b>Защита:</b> {p['def']}"]
    if s["combat"]:
        lines = []
        for e in s["combat"]["enemies"]:
            m = MONSTERS[e["kind"]]
            lines.append(f"— {m['name']}: {hp_bar(e['hp'], m['baseHp'])} ({e['hp']}/{m['baseHp']})")
        parts.append("<b>Противники:</b>\n" + "\n".join(lines))
        parts.append(f"<i>Парирование:</i> {s['combat']['guard']}")
    if s["bag"]:
        parts.append("<b>Сумка:</b> " + ", ".join(s["bag"]))
    if s["runes"]:
        parts.append("<b>Руны:</b> " + ", ".join(s["runes"]))
    return "\n".join(parts)

async def render_scene(uid):
    s = get_state(uid)
    scene = SCENES[s["sceneId"]]
    text = f"<b>{scene['title']}</b>\n\n{scene['text']}\n\n{fmt_state(uid)}"
    kb = kb_choices(scene, s)
    return text, kb

async def send_scene(message_or_cb, uid):
    text, kb = await render_scene(uid)
    if isinstance(message_or_cb, types.CallbackQuery):
        await message_or_cb.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await message_or_cb.answer()
    else:
        await message_or_cb.answer(text, reply_markup=kb, disable_web_page_preview=True)

@dp.message_handler(commands=["start"])
async def cmd_start(m: types.Message):
    uid = m.from_user.id
    USERS.pop(uid, None)  # reset
    await enter_scene(uid, "start")
    await send_scene(m, uid)

@dp.callback_query_handler(lambda c: c.data.startswith("hint"))
async def cb_hint(c: types.CallbackQuery):
    uid = c.from_user.id
    s = get_state(uid)
    scene = SCENES[s["sceneId"]]
    hint = scene.get("hint") or "Прислушайся к миру — он подскажет."
    await c.answer(hint, show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("to:"))
async def cb_to(c: types.CallbackQuery):
    uid = c.from_user.id
    target = c.data[3:]
    s = get_state(uid)
    ch_need_ok = True
    # check needs for choice if any
    # we can't easily map from button to scene choice; do minimal checks on arrival
    if target in SCENES:
        sc = SCENES[target]
        # basic runes requirement if present on button (we encoded in `need` only in certain scenes)
        # We'll gate on arrival with logs.
    await enter_scene(uid, target)
    await send_scene(c, uid)

@dp.callback_query_handler(lambda c: c.data.startswith("p:"))
async def cb_puzzle_answer(c: types.CallbackQuery):
    uid = c.from_user.id
    s = get_state(uid)
    scene = SCENES[s["sceneId"]]
    if scene["type"] != "puzzle":
        return await c.answer()
    i = int(c.data.split(":")[1])
    opt = scene["puzzle"]["opts"][i]
    target = scene["puzzle"]["succ"] if opt["ok"] else scene["puzzle"]["fail"]
    await enter_scene(uid, target)
    await send_scene(c, uid)

def next_enemy_index(cmb):
    for i,e in enumerate(cmb["enemies"]):
        if e["hp"]>0: return i
    return -1

async def enemy_turn(uid, c: types.CallbackQuery=None):
    s = get_state(uid)
    if not s["combat"]: return
    cmb = s["combat"]
    alive = [e for e in cmb["enemies"] if e["hp"]>0]
    if not alive:
        after = SCENES[cmb["sceneId"]].get("afterWin","start")
        s["combat"] = None
        await enter_scene(uid, after)
        if c: await send_scene(c, uid)
        return
    idx = next_enemy_index(cmb)
    ekind = cmb["enemies"][idx]["kind"]
    raw = rnd(*MONSTERS[ekind]["dmg"])
    dmg = max(0, raw - s["player"]["def"])
    if cmb["guard"]>0:
        dmg = 0
        cmb["guard"] -= 1
    # fate saves from lethal
    if dmg >= s["player"]["hp"] and s["player"]["fate"]>0:
        dmg = max(0, s["player"]["hp"]-1)
        s["player"]["fate"] -= 1
    s["player"]["hp"] = clamp(s["player"]["hp"] - dmg, 0, s["player"]["maxHp"])
    # defeat?
    if s["player"]["hp"] <= 0:
        after = SCENES[cmb["sceneId"]].get("afterLose","game-over")
        s["combat"] = None
        await enter_scene(uid, after)
        if c: await send_scene(c, uid)
        return
    cmb["turn"] = "player"
    if c: await send_scene(c, uid)

@dp.callback_query_handler(lambda c: c.data.startswith("act:"))
async def cb_act(c: types.CallbackQuery):
    uid = c.from_user.id
    s = get_state(uid)
    if not s["combat"]:
        return await c.answer()
    act = c.data.split(":")[1]
    cmb = s["combat"]
    if act == "hit":
        idx = next_enemy_index(cmb)
        if idx==-1:
            return await c.answer()
        e = cmb["enemies"][idx]
        dmg = rnd(*s["player"]["atk"])
        e["hp"] = clamp(e["hp"] - dmg, 0, 999)
        cmb["turn"] = "enemy"
        await send_scene(c, uid)
        await enemy_turn(uid, c)
    elif act == "parry":
        cmb["guard"] += 1
        cmb["turn"] = "enemy"
        await send_scene(c, uid)
        await enemy_turn(uid, c)

@dp.callback_query_handler(lambda c: c.data.startswith("use:"))
async def cb_use(c: types.CallbackQuery):
    uid = c.from_user.id
    name = c.data[4:]
    s = get_state(uid)
    if name not in s["bag"]:
        return await c.answer()
    s["bag"].remove(name)
    it = ITEMS.get(name, {})
    if it.get("type") == "heal":
        s["player"]["hp"] = clamp(s["player"]["hp"] + it["amount"], 0, s["player"]["maxHp"])
    elif it.get("type") == "buff":
        s["player"]["atk"][0] += it["amount"]
        s["player"]["atk"][1] += it["amount"]
    elif it.get("type") == "def":
        if s["combat"]:
            s["combat"]["guard"] += it["amount"]
    await send_scene(c, uid)

# Webhook setup
async def on_startup(app: web.Application):
    if WEBHOOK_BASE:
        await bot.set_webhook(f"{WEBHOOK_BASE}/{WEBHOOK_SECRET}", drop_pending_updates=True)
        logging.info("Webhook set to %s/%s", WEBHOOK_BASE, WEBHOOK_SECRET)
    else:
        logging.warning("WEBHOOK_BASE not set; bot will still start, but Telegram can't reach it.")

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    await bot.session.close()

async def health(request):
    return web.Response(text="ok")

def make_app():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    app.router.add_post(f'/{WEBHOOK_SECRET}', dp.webhook_handler)
    app.router.add_get('/healthz', health)
    return app

if __name__ == "__main__":
    # Use aiohttp.web directly (Render web service expects listener on $PORT)
    web.run_app(make_app(), host=WEBAPP_HOST, port=WEBAPP_PORT)
