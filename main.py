

import os
import json
import random
import unicodedata
import httpx
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from fastapi import FastAPI, Request, HTTPException

# === ENV ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret123")
WEBHOOK_BASE = os.getenv("WEBHOOK_BASE", "")  # e.g. https://your-service.onrender.com
TG = f"https://api.telegram.org/bot{BOT_TOKEN}"

# === FASTAPI ===
app = FastAPI()

# === UTILS ===
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", (s or "")).strip().lower()
    s = s.replace("ё", "е")
    return s

async def tg(method: str, payload: dict):
    async with httpx.AsyncClient(timeout=20) as cl:
        r = await cl.post(f"{TG}/{method}", json=payload)
        r.raise_for_status()
        return r.json()

def kb(rows: List[List[Dict[str, str]]]) -> dict:
    # rows: [[{"text":"...", "data":"..."}], ...]
    return {"inline_keyboard": [[{"text":b["text"], "callback_data":b["data"]} for b in row] for row in rows]}

def hp_bar(cur: int, mx: int, width: int = 10) -> str:
    cur = max(0, min(cur, mx))
    filled = int(round(width * (cur / mx if mx else 0)))
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

# === IMAGES (заменишь свои при желании) ===
IMG = {
    "village": "https://images.unsplash.com/photo-1533105079780-92b9be482077",
    "forest_trail": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee",
    "rune_sun": "https://images.unsplash.com/photo-1617191519009-8f6a0c2e6c7f",
    "leshy": "https://images.unsplash.com/photo-1509043759401-136742328bb3",
    "herbs": "https://images.unsplash.com/photo-1520256862855-398228c41684",
    "brew": "https://images.unsplash.com/photo-1556909190-97b8f3f2ab1b",
    "mist": "https://images.unsplash.com/photo-1504898770365-14faca6f86e1",
    "onion": "https://images.unsplash.com/photo-1504196606672-aef5c9cefc92",
    "treasure": "https://images.unsplash.com/photo-1549880338-65ddcdfd017b",
    "frost": "https://images.unsplash.com/photo-1519681393784-d120267933ba",
    "forge": "https://images.unsplash.com/photo-1519710164239-da123dc03ef4",
    "werewolf": "https://images.unsplash.com/photo-1482192505345-5655af888cc4",
    "scissors": "https://images.unsplash.com/photo-1500021802231-0a1ff452b1d1",
    "willow": "https://images.unsplash.com/photo-1501785888041-af3ef285b470",
    "cave": "https://images.unsplash.com/photo-1454179083322-198bb4daae1b",
    "dark": "https://images.unsplash.com/photo-1454179083322-198bb4daae1b?ix=dark",
    "wyrm": "https://images.unsplash.com/photo-1469474968028-56623f02e42e",
    "sphinx": "https://images.unsplash.com/photo-1494738073002-80e2b34f3f49",
    "altar": "https://images.unsplash.com/photo-1482192505345-5655af888cc4?ix=altar",
    "finale": "https://images.unsplash.com/photo-1519681393784-d120267933ba?ix=finale",
    "bad": "https://images.unsplash.com/photo-1518837695005-2083093ee35b"
}

# === GAME DATA ===
@dataclass
class Combat:
    enemy: str
    max_hp: int
    hp: int
    img: str
    # базовый урон врага на ход
    dmg_min: int
    dmg_max: int
    # описание/подсказка
    hint: str
    # следующая локация при победе
    win_to: str
    # особенность (модификаторы)
    trait: Optional[str] = None  # 'needs_silver', 'weak_to_igni', 'stuns_with_amulet', 'weak_to_aard'

@dataclass
class Session:
    max_hp: int = 50
    hp: int = 50
    level: int = 1
    xp: int = 0
    dmg_min: int = 6
    dmg_max: int = 12
    yrden_turns: int = 0
    _axii_last_success: bool = False
    _burned_item_last: str = ""
    location: str = "intro"
    inventory: List[str] = field(default_factory=list)
    finished: bool = False
    # активный бой
    combat: Optional[Combat] = None
    # единоразовое спасение от летального удара
    fate: int = 1

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

# === NODES ===
NODES = {
    "intro": {
        "img": IMG["village"],
        "text": (
            "🛡 *Коловрат — ведьмак Древней Руси*\n\n"
            "Тебя призвали в северный уезд: ночью в лесу шепчут огоньки, в деревне пропадают люди, "
            "на болоте воет Волколак, а в каменных кругах стынет Морозница. Коловоротный амулет старцев "
            "обещает дорогу к алтарю, где скрыта причина беды. Пройди тропы, избы, курганы, святилища и пещеры, "
            "сразись с чудовищами, разгадай руны и собери то, что поможет выжить. На алтаре завершится круг — и зло падёт.\n\n"
            "У тебя 8 жизней. Всё управление — *кнопками*. Подсказки появляются по запросу.\n"
            "Готов начать путь?"
        ),
        "buttons": [
            [{"text": "В путь", "to": "trail"}, {"text": "Подсказка", "hint": "След держись ближе к деревне, затем уходи на северную тропу."}]
        ]
    },

    "trail": {
        "img": IMG["forest_trail"],
        "text": "🌲 Тропа у кромки леса. Следы ведут в чащу. Куда идти?",
        "buttons": [
            [{"text": "Налево (к рунам)", "to": "rune_sun"}, {"text": "Направо (к болотам)", "to": "willow_lights"}],
            [{"text": "Подсказка", "hint": "Леший любит тьму — сперва найди то, что её режет."}]
        ]
    },

    "rune_sun": {
        "img": IMG["rune_sun"],
        "text": "☀️ Камень с руной. Надпись: «То, что режет тьму».",
        "buttons": [
            [{"text": "Свет", "to": "leshy_spawn"}, {"text": "Нож", "to": "punish_back_trail"}, {"text": "Ветер", "to": "punish_back_trail"}],
            [{"text": "Подсказка", "hint": "Ответ — то, что невозможно заточить."}]
        ]
    },

    "punish_back_trail": {
        "img": IMG["bad"],
        "text": "Ты оступился — нечисть шепчет в темноте. −1 жизнь.",
        "hp_delta": -1,
        "buttons": [
            [{"text": "Вернуться к тропе", "to": "trail"}]
        ]
    },

    "leshy_spawn": {
        "img": IMG["leshy"],
        "text": "🌿 В чаще выходит Леший. Ветви шевелятся.",
        "combat": Combat(
            enemy="Леший",
            max_hp=60, hp=60, img=IMG["leshy"],
            dmg_min=1, dmg_max=3,
            hint="Огонь против древних — сила. Знак *Игни* жжёт кору.",
            win_to="herb_patch",
            trait="weak_to_igni"
        )
    },

    "herb_patch": {
        "img": IMG["herbs"],
        "text": "🌾 Поляна трав. Сорвёшь немного?",
        "buttons": [
            [{"text": "Взять травы", "data": "take:травы:brew_hut"}],
            [{"text": "Идти дальше без трав", "to": "mist_wraith"}],
            [{"text": "Подсказка", "hint": "Травы пригодятся, чтобы сварить зелье перед туманником."}]
        ]
    },

    "brew_hut": {
        "img": IMG["brew"],
        "text": "🧪 В старой избе можно сварить зелье.",
        "buttons": [
            [{"text": "Сварить зелье", "data": "brew:зелье:mist_wraith"}],
            [{"text": "Выйти без зелья", "to": "mist_wraith"}]
        ]
    },

    "mist_wraith": {
        "img": IMG["mist"],
        "text": "💨 В тумане мерцает туманник — бьёт из засады.",
        "combat": Combat(
            enemy="Туманник",
            max_hp=70, hp=70, img=IMG["mist"],
            dmg_min=1, dmg_max=2,
            hint="Зелье повышает устойчивость. Огонь работает, но слабее, чем по лешему.",
            win_to="onion_riddle"
        )
    },

    "onion_riddle": {
        "img": IMG["onion"],
        "text": "🧩 «Сидит дед, во сто шуб одет».",
        "buttons": [
            [{"text": "Лук", "to": "amulet_room"}, {"text": "Капуста", "to": "punish_back_trail"}],
            [{"text": "Подсказка", "hint": "Его чистят до слёз."}]
        ]
    },

    "amulet_room": {
        "img": IMG["treasure"],
        "text": "🪬 На пьедестале — коловоротный амулет.",
        "buttons": [
            [{"text": "Взять амулет", "data": "take:амулет:frost_circles"}],
            [{"text": "Оставить и идти дальше", "to": "frost_circles"}]
        ]
    },

    "frost_circles": {
        "img": IMG["frost"],
        "text": "❄️ Каменные круги — Морозница витает над льдом.",
        "combat": Combat(
            enemy="Морозница",
            max_hp=85, hp=85, img=IMG["frost"],
            dmg_min=2, dmg_max=3,
            hint="Амулет помогает отбить холод: используйте его в бою.",
            win_to="forge"
        )
    },

    "forge": {
        "img": IMG["forge"],
        "text": "⚒️ В пустой кузне наковальня мерцает. Возьмёшь клинок?",
        "buttons": [
            [{"text": "Взять серебряный клинок", "data": "take:серебряный клинок:werewolf"}],
            [{"text": "Оставить и идти дальше", "to": "werewolf"}]
        ]
    },

    "werewolf": {
        "img": IMG["werewolf"],
        "text": "🐺 Из кургана выходит Волколак.",
        "combat": Combat(
            enemy="Волколак",
            max_hp=100, hp=100, img=IMG["werewolf"],
            dmg_min=2, dmg_max=4,
            hint="Серебряный клинок рвёт плоть чудовища куда сильнее.",
            win_to="scissors_riddle",
            trait="needs_silver"
        )
    },

    "scissors_riddle": {
        "img": IMG["scissors"],
        "text": "✂️ «Два кольца, два конца, посредине гвоздик».",
        "buttons": [
            [{"text": "Ножницы", "to": "bog_willows"}, {"text": "Клещи", "to": "punish_back_trail"}, {"text": "Очки", "to": "punish_back_trail"}],
            [{"text": "Подсказка", "hint": "Ею режут ткань, бумагу."}]
        ]
    },

    "willow_lights": {
        "img": IMG["willow"],
        "text": "🔵 Болотные огоньки манят прочь от тропы.",
        "buttons": [
            [{"text": "Вернуться", "to": "trail"}, {"text": "Идти на огни (опасно)", "to": "punish_back_trail"}],
            [{"text": "Подсказка", "hint": "Огоньки заводят путников на гибель."}]
        ]
    },

    "bog_willows": {
        "img": IMG["cave"],
        "text": "🔥 Вход в пещеру. У стены — факел.",
        "buttons": [
            [{"text": "Взять факел", "data": "take:факел:dark_tunnel"}],
            [{"text": "Идти без факела", "to": "dark_tunnel"}]
        ]
    },

    "dark_tunnel": {
        "img": IMG["dark"],
        "text": "🌑 Ходы уходят во тьму. Чем осветишь путь?",
        "buttons": [
            [{"text": "Зажечь факел", "to": "wyrm_lair"}],
            [{"text": "Идти наощупь (опасно)", "to": "punish_back_trail"}]
        ]
    },

    "wyrm_lair": {
        "img": IMG["wyrm"],
        "text": "🐉 Под сводом шевелится змей.",
        "combat": Combat(
            enemy="Змей",
            max_hp=90, hp=90, img=IMG["wyrm"],
            dmg_min=2, dmg_max=3,
            hint="Знак *Аард* (ветер) сбивает чудовище.",
            win_to="sphinx_riddle",
            trait="weak_to_aard"
        )
    },

    "sphinx_riddle": {
        "img": IMG["sphinx"],
        "text": "🧠 «Утром на четырёх, днём на двух, вечером на трёх».",
        "buttons": [
            [{"text": "Человек", "to": "altar"}, {"text": "Конь", "to": "punish_back_trail"}, {"text": "Старик", "to": "punish_back_trail"}],
            [{"text": "Подсказка", "hint": "Речь о жизни от младенца до старости."}]
        ]
    },

    "altar": {
        "img": IMG["altar"],
        "text": "⛨ У алтаря ты должен произнести слово силы.",
        "buttons": [
            [{"text": "Произнести «Коловрат»", "to": "finale"}],
            [{"text": "Подсказка", "hint": "Круг, вращение, защита — символ рода."}]
        ]
    },

    "finale": {
        "img": IMG["finale"],
        "text": "🏁 Зло рассеяно. Ты получаешь трофей и славу.\nХочешь снова? Нажми «Начать заново».",
        "buttons": [
            [{"text": "Начать заново", "to": "intro"}]
        ]
    },
}


# === EXPANSION: images & new nodes ===
IMG.update({
    "ruins": "https://images.unsplash.com/photo-1483721310020-03333e577078",
    "idol": "https://images.unsplash.com/photo-1523419409543-1882bd33f2e0",
    "witch": "https://images.unsplash.com/photo-1526318472351-c75fcf070305",
    "bog2": "https://images.unsplash.com/photo-1533587851505-d119e13fa0d7",
    "shadow": "https://images.unsplash.com/photo-1506744038136-46273834b3fb",
    "ognevic": "https://images.unsplash.com/photo-1519681393784-d120267933ba",
    "cave": "https://images.unsplash.com/photo-1507502707541-f369a3b18502",
    "serpent": "https://images.unsplash.com/photo-1515548212256-91d67ea4b222",
    "ghost": "https://images.unsplash.com/photo-1514511542222-1f2fc2d6a2fa",
    "ghoul": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee",
    "crypt": "https://images.unsplash.com/photo-1482192596544-9eb780fc7f66",
    "ruins_inner": "https://images.unsplash.com/photo-1549880338-65ddcdfd017b",
})

NEW_NODES = {
    "ruins_path": {
        "img": IMG["ruins"],
        "text": "🏚 *Старая дорога к руинам.*\n\nДорога уходит в каменистый яр, где когда-то стоял храм. На мшистых плитах — следы от копыт и круги, будто кто-то двигал камни.",
        "buttons": [
            [{"text": "К воротам руин", "to": "ruins_gate"}],
            [{"text": "Вернуться к тропе", "to": "trail"}]
        ]
    },
    "ruins_gate": {
        "img": IMG["idol"],
        "text": "🗿 *Каменный идол у ворот.*\n\nЛицо без глаз, рот — щель. Слышен низкий гул: идол оживает.",
        "combat": Combat(enemy="Каменный идол", max_hp=110, hp=110, img=IMG["idol"], dmg_min=3, dmg_max=8, hint="Камень терпелив, но боится огня. Игни прожигает трещины.", win_to="ruins_inner", trait="stone_skin"),
        "buttons": [
            [{"text": "Удар", "data": "fight:hit"}, {"text": "Игни", "data": "fight:igni"}],
            [{"text": "Аард", "data": "fight:aard"}, {"text": "Квен", "data": "fight:quen"}],
            [{"text": "Ирден", "data": "fight:yrden"}, {"text": "Аксий", "data": "fight:axii"}],
            [{"text": "Выпить зелье", "data": "fight:potion"}, {"text": "Показать амулет", "data": "fight:amulet"}],
            [{"text": "Подсказка", "data": "hint:combat"}],
        ]
    },
    "ruins_inner": {
        "img": IMG["ruins_inner"],
        "text": "🏛 *Внутренние залы руин.*\n\nПыльные колонны, шёпот сквозняка, на плитах — руны старцев. В нишах — разбитые сосуды, в углу — следы костра и кости мелких зверей.",
        "buttons": [
            [{"text": "🔍 Осмотреть руны", "to": "ruins_riddle"}],
            [{"text": "Идти к белой ведьме", "to": "white_witch_spawn"}],
            [{"text": "Вернуться к тропе", "to": "trail"}]
        ]
    },
    "ruins_riddle": {
        "img": IMG["ruins_inner"],
        "text": "На плите выгравировано: «Что утром на четырёх, днём на двух, вечером на трёх?»",
        "buttons": [
            [{"text": "Человек", "to": "ruins_riddle_right"}],
            [{"text": "Волк", "to": "ruins_riddle_wrong"}],
            [{"text": "Идол", "to": "ruins_riddle_wrong"}]
        ]
    },
    "ruins_riddle_right": {
        "img": IMG["ruins_inner"],
        "text": "Руны теплеют. В нише щёлкнуло.",
        "buttons": [
            [{"text": "Взять ключ", "data": "take:ключ:white_witch_spawn"}]
        ]
    },
    "ruins_riddle_wrong": {
        "img": IMG["ruins_inner"],
        "text": "Плита дёрнулась — камень ударил по ноге.",
        "hp_delta": -10,
        "buttons": [
            [{"text": "Отойти к залу", "to": "ruins_inner"}]
        ]
    },
    "white_witch_spawn": {
        "img": IMG["witch"],
        "text": "👻 *Ведьма в белом* выходит из тени колонны. Шепчет — и холод поднимается по спине.",
        "combat": Combat(enemy="Ведьма в белом", max_hp=80, hp=80, img=IMG["witch"], dmg_min=3, dmg_max=7, hint="Страх стягивает грудь. Поможет Аксий или решительный удар.", win_to="bog_path", trait="fear"),
        "buttons": [
            [{"text": "Удар", "data": "fight:hit"}, {"text": "Игни", "data": "fight:igni"}],
            [{"text": "Аард", "data": "fight:aard"}, {"text": "Квен", "data": "fight:quen"}],
            [{"text": "Ирден", "data": "fight:yrden"}, {"text": "Аксий", "data": "fight:axii"}],
            [{"text": "Выпить зелье", "data": "fight:potion"}, {"text": "Показать амулет", "data": "fight:amulet"}],
            [{"text": "Подсказка", "data": "hint:combat"}],
        ]
    },
    "bog_path": {
        "img": IMG["bog2"],
        "text": "🌫 *Глубокое болото.*\n\nОгни мерцают между кочками, тростник шепчет. Вязкая тропа уводит всё дальше.",
        "buttons": [
            [{"text": "🛶 Помочь старику переправить лодку", "to": "bog_oldman"}],
            [{"text": "Пройти мимо", "to": "bog_shadow_spawn"}],
            [{"text": "К шепчущему огню", "to": "ognevic_spawn"}],
            [{"text": "Назад к развилке", "to": "trail"}]
        ]
    },
    "bog_oldman": {
        "img": IMG["bog2"],
        "text": "Старик кивает и благодарит. Но силы уходит на вёсла.",
        "hp_delta": -10,
        "buttons": [
            [{"text": "Получить зелье и идти дальше", "data": "take:зелье:bog_shadow_spawn"}]
        ]
    },
    "bog_shadow_spawn": {
        "img": IMG["shadow"],
        "text": "🕯 *Болотная тень* выплывает из тумана, шевелясь, как дым.",
        "combat": Combat(enemy="Болотная тень", max_hp=70, hp=70, img=IMG["shadow"], dmg_min=2, dmg_max=6, hint="Тень ускользает — попадать сложно. Аард срывает маску.", win_to="cave_entrance", trait="evasive"),
        "buttons": [
            [{"text": "Удар", "data": "fight:hit"}, {"text": "Игни", "data": "fight:igni"}],
            [{"text": "Аард", "data": "fight:aard"}, {"text": "Квен", "data": "fight:quen"}],
            [{"text": "Ирден", "data": "fight:yrden"}, {"text": "Аксий", "data": "fight:axii"}],
            [{"text": "Выпить зелье", "data": "fight:potion"}, {"text": "Показать амулет", "data": "fight:amulet"}],
            [{"text": "Подсказка", "data": "hint:combat"}],
        ]
    },
    "ognevic_spawn": {
        "img": IMG["ognevic"],
        "text": "🔥 *Огневик* вспыхивает прямо из трясины, сжигая тростник, жар обжигает лицо.",
        "combat": Combat(enemy="Огневик", max_hp=85, hp=85, img=IMG["ognevic"], dmg_min=3, dmg_max=9, hint="Огонь не терпит пустоты. Аард срывает языки пламени.", win_to="cave_entrance", trait="burn_items"),
        "buttons": [
            [{"text": "Удар", "data": "fight:hit"}, {"text": "Игни", "data": "fight:igni"}],
            [{"text": "Аард", "data": "fight:aard"}, {"text": "Квен", "data": "fight:quen"}],
            [{"text": "Ирден", "data": "fight:yrden"}, {"text": "Аксий", "data": "fight:axii"}],
            [{"text": "Выпить зелье", "data": "fight:potion"}, {"text": "Показать амулет", "data": "fight:amulet"}],
            [{"text": "Подсказка", "data": "hint:combat"}],
        ]
    },
    "cave_entrance": {
        "img": IMG["cave"],
        "text": "🕳 *Вход в пещеру.*\n\nХолодный воздух тянет снизу. Стены изрезаны, будто когтями. Где-то глубже капает вода.",
        "buttons": [
            [{"text": "🪨 Осмотреть стену (свиток огня)", "to": "cave_scroll"}],
            [{"text": "👂 Прислушаться к эху", "to": "cave_echo"}],
            [{"text": "Спуститься ниже", "to": "serpent_spawn"}],
            [{"text": "Ответвление к нише", "to": "ghost_spawn"}],
            [{"text": "Вернуться к болоту", "to": "bog_path"}]
        ]
    },
    "cave_scroll": {
        "img": IMG["cave"],
        "text": "В трещине стены спрятан свиток.",
        "buttons": [
            [{"text": "Взять свиток огня", "data": "take:свиток огня:cave_entrance"}]
        ]
    },
    "cave_echo": {
        "img": IMG["cave"],
        "text": "Эхо шепчет: «Что тяжелее — пуд ваты или пуд железа?»",
        "buttons": [
            [{"text": "Одинаково", "to": "echo_right"}],
            [{"text": "Железо", "to": "echo_wrong"}]
        ]
    },
    "echo_right": {
        "img": IMG["cave"],
        "text": "Голос одобряет. ты чувствуешь прилив сил.",
        "hp_delta": +5,
        "buttons": [
            [{"text": "Вернуться к развилке", "to": "cave_entrance"}]
        ]
    },
    "echo_wrong": {
        "img": IMG["cave"],
        "text": "Эхо смеётся и гасит факел.",
        "hp_delta": -5,
        "buttons": [
            [{"text": "Вернуться к развилке", "to": "cave_entrance"}]
        ]
    },
    "serpent_spawn": {
        "img": IMG["serpent"],
        "text": "🐍 *Змей трёхглавый* извивается, каждая голова шипит по-своему.",
        "combat": Combat(enemy="Змей трёхглавый", max_hp=120, hp=120, img=IMG["serpent"], dmg_min=3, dmg_max=8, hint="Руби быстро — головы промахиваются, но если попадут — будет больно.", win_to="crypt_hall", trait="double_strike"),
        "buttons": [
            [{"text": "Удар", "data": "fight:hit"}, {"text": "Игни", "data": "fight:igni"}],
            [{"text": "Аард", "data": "fight:aard"}, {"text": "Квен", "data": "fight:quen"}],
            [{"text": "Ирден", "data": "fight:yrden"}, {"text": "Аксий", "data": "fight:axii"}],
            [{"text": "Выпить зелье", "data": "fight:potion"}, {"text": "Показать амулет", "data": "fight:amulet"}],
            [{"text": "Подсказка", "data": "hint:combat"}],
        ]
    },
    "ghost_spawn": {
        "img": IMG["ghost"],
        "text": "⚰️ *Призрак воина* выходит из тьмы ниши, шепчет древние клятвы.",
        "combat": Combat(enemy="Призрак воина", max_hp=75, hp=75, img=IMG["ghost"], dmg_min=2, dmg_max=7, hint="Ему не по душе грубая сила. Заклинания и амулет помогут.", win_to="crypt_hall", trait="reflect"),
        "buttons": [
            [{"text": "Удар", "data": "fight:hit"}, {"text": "Игни", "data": "fight:igni"}],
            [{"text": "Аард", "data": "fight:aard"}, {"text": "Квен", "data": "fight:quen"}],
            [{"text": "Ирден", "data": "fight:yrden"}, {"text": "Аксий", "data": "fight:axii"}],
            [{"text": "Выпить зелье", "data": "fight:potion"}, {"text": "Показать амулет", "data": "fight:amulet"}],
            [{"text": "Подсказка", "data": "hint:combat"}],
        ]
    },
    "crypt_hall": {
        "img": IMG["crypt"],
        "text": "🕯 *Зал крипты.*\n\nСвечи стекли в каменные чаши, запах ладана и железа. Плита алтаря закрыта печатью.",
        "buttons": [
            [{"text": "⚡ Сломать печать (−15 HP)", "to": "crypt_break"}],
            [{"text": "🧿 Применить амулет", "to": "crypt_open"}],
            [{"text": "Вернуться к тропе", "to": "trail"}]
        ]
    },
    "crypt_break": {
        "img": IMG["crypt"],
        "text": "Ты срываешь печать силой.",
        "hp_delta": -15,
        "buttons": [
            [{"text": "К финальному алтарю", "to": "trail"}]
        ]
    },
    "crypt_open": {
        "img": IMG["crypt"],
        "text": "Амулет теплеет, руны растворяются.",
        "buttons": [
            [{"text": "К финальному алтарю", "to": "trail"}]
        ]
    },
    
    "scorpion_path": {
        "img": "https://images.unsplash.com/photo-1609587314425-c65f63dc67d3",
        "text": "🏜 *Пустынная расщелина.*\\n\\nУзкий проход между каменными стенами. В песке поблёскивают хитиновые пластины.",
        "buttons": [
            [{"text": "Осмотреть песок", "to": "scorpion_spawn"}],
            [{"text": "Вернуться к тропе", "to": "trail"}]
        ]
    },
    "scorpion_spawn": {
        "img": "https://images.unsplash.com/photo-1618005182384-a83a8d0fa4c1",
        "text": "🦂 *Песчаный скорпион* вырывается из песка, клешни щёлкают, жало блестит.",
        "combat": Combat(enemy="Песчаный скорпион", max_hp=85, hp=85,
            img="https://images.unsplash.com/photo-1618005182384-a83a8d0fa4c1",
            dmg_min=4, dmg_max=9,
            hint="Ядовитое жало. Используй Квен или Аард, чтобы пережить яд.",
            win_to="trail", trait="poison"),
        "buttons": [
            [{"text": "Удар", "data": "fight:hit"}, {"text": "Игни", "data": "fight:igni"}],
            [{"text": "Аард", "data": "fight:aard"}, {"text": "Квен", "data": "fight:quen"}],
            [{"text": "Ирден", "data": "fight:yrden"}, {"text": "Аксий", "data": "fight:axii"}],
            [{"text": "Выпить зелье", "data": "fight:potion"}, {"text": "Показать амулет", "data": "fight:amulet"}],
            [{"text": "Подсказка", "data": "hint:combat"}],
        ]
    },
    "ghoul_spawn": {
        "img": IMG["ghoul"],
        "text": "🩸 *Вурдалак* крадётся, зубы поблёскивают в темноте.",
        "combat": Combat(enemy="Вурдалак", max_hp=90, hp=90, img=IMG["ghoul"], dmg_min=3, dmg_max=7, hint="Ранишь — он пьёт кровь. Бей быстро и не подпускай.", win_to="trail", trait="lifesteal"),
        "buttons": [
            [{"text": "Удар", "data": "fight:hit"}, {"text": "Игни", "data": "fight:igni"}],
            [{"text": "Аард", "data": "fight:aard"}, {"text": "Квен", "data": "fight:quen"}],
            [{"text": "Ирден", "data": "fight:yrden"}, {"text": "Аксий", "data": "fight:axii"}],
            [{"text": "Выпить зелье", "data": "fight:potion"}, {"text": "Показать амулет", "data": "fight:amulet"}],
            [{"text": "Подсказка", "data": "hint:combat"}],
        ]
    },
}

try:
    NODES.update(NEW_NODES)
    if "trail" in NODES and isinstance(NODES["trail"].get("buttons"), list):
        NODES["trail"]["buttons"].append([{"text": "Пойти к руинам", "to": "ruins_path"}])
        NODES["trail"]["buttons"].append([{"text": "Свернуть к болоту", "to": "bog_path"}])
        NODES["trail"]["buttons"].append([{"text": "В пещеру (ответвление)", "to": "cave_entrance"}])
    elif "intro" in NODES and isinstance(NODES["intro"].get("buttons"), list):
        NODES["intro"]["buttons"].append([{"text": "Пойти к руинам", "to": "ruins_path"}])
        NODES["intro"]["buttons"].append([{"text": "Свернуть к болоту", "to": "bog_path"}])
        NODES["intro"]["buttons"].append([{"text": "В пещеру (ответвление)", "to": "cave_entrance"}])
except Exception as e:
    pass


# === EXPANSION (Mirror Hall Riddle) ===
IMG.update({
    "mirror_hall": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?ixlib=rb-4.0.3&auto=format&fit=crop&w=1280&q=80"
})

NEW_NODES_MIRROR = {
    "mirror_hall": {
        "img": IMG["mirror_hall"],
        "text": "🪞 *Зеркальный зал.*\n\nПлитки пола отражают тебя, словно вода. На стене выгравировано: «Ответь — и путь откроется».",
        "buttons": [
            [{"text": "Подойти к надписи", "to": "mirror_riddle"}],
            [{"text": "Вернуться назад", "to": "trail"}]
        ]
    },
    "mirror_riddle": {
        "img": IMG["mirror_hall"],
        "text": "Загадка: *Что можно сломать, не касаясь?*",
        "buttons": [
            [{"text": "Тишину", "to": "mirror_right"}],
            [{"text": "Лёд", "to": "mirror_wrong"}],
            [{"text": "Клятву", "to": "mirror_wrong"}]
        ]
    },
    "mirror_right": {
        "img": IMG["mirror_hall"],
        "text": "Зеркала звенят, и из стены выезжает ниша со светящимся осколком.",
        "buttons": [
            [{"text": "Взять осколок зеркала", "data": "take:осколок зеркала:mirror_hall"}]
        ]
    },
    "mirror_wrong": {
        "img": IMG["mirror_hall"],
        "text": "Эхо насмехается, зеркала мутнеют — тебе становится не по себе.",
        "hp_delta": -7,
        "buttons": [
            [{"text": "Попробовать снова", "to": "mirror_riddle"}],
            [{"text": "Отступить", "to": "mirror_hall"}]
        ]
    }
}

try:
    NODES.update(NEW_NODES_MIRROR)
    # Ссылка из стартовой тропы
    if "trail" in NODES and isinstance(NODES["trail"].get("buttons"), list):
        NODES["trail"]["buttons"].append([{"text": "Зеркальный зал", "to": "mirror_hall"}])
except Exception:
    pass

# === COMBAT ENGINE ===
def build_combat_message(s: Session) -> (str, dict, str):
    c = s.combat
    assert c is not None
    title = f"*{c.enemy}*"
    enemy_hp = f"HP {c.hp}/{c.max_hp}  [{hp_bar(c.hp, c.max_hp)}]"
    me_hp = f"Твои жизни: {s.hp}/8  [{hp_bar(s.hp, 8)}]"
    effect_hint = "Нажми «Подсказка», если нужно."
    rows = [
        [{"text": "Удар", "data": "fight:hit"},
         {"text": "Игни", "data": "fight:igni"}],
        [{"text": "Аард", "data": "fight:aard"},
         {"text": "Выпить зелье", "data": "fight:potion"}],
        [{"text": "Показать амулет", "data": "fight:amulet"},
         {"text": "Подсказка", "data": "hint:combat"}],
    ]
    caption = f"{title}\n{enemy_hp}\n{me_hp}\n\n{effect_hint}"
    return caption, kb(rows), c.img

def calc_player_damage(action: str, s: Session, c: Combat) -> int:
    if action in ("potion", "quen", "yrden", "axii"):
        return 0
    if action == "hit":
        lo, hi = s.dmg_min, s.dmg_max
    elif action == "igni":
        lo, hi = max(1, s.dmg_min-1), s.dmg_max
    elif action == "aard":
        lo, hi = max(1, s.dmg_min-2), max(s.dmg_min, s.dmg_max-1)
    elif action == "amulet":
        if c.trait == "stuns_with_amulet":
            return 12
        return 0
    else:
        lo, hi = 0, 0
    dmg = random.randint(lo, hi)
    if c.trait == "needs_silver" and (action == "hit") and have(s, "серебряный клинок"):
        dmg += 10
    if c.trait == "weak_to_igni" and action == "igni":
        dmg += 8
    if c.trait == "weak_to_aard" and action == "aard":
        dmg += 8
    trait = (c.trait or "").strip()
    if trait == "evasive":
        if random.random() < 0.25:
            dmg = 0
    if trait == "stone_skin":
        dmg = max(0, int(dmg * 0.7))
    if trait == "fear":
        dmg = int(dmg * 0.75)
    return max(0, dmg)

def calc_enemy_damage(s: Session, c: Combat, player_action: str, potion_used: bool) -> int:
    s._axii_last_success = False
    s._burned_item_last = ""
    dmg = random.randint(c.dmg_min, c.dmg_max)
    dmg = int(round(dmg * 1.35))
    if dmg < 1:
        dmg = 1
    if player_action == "quen":
        dmg = max(0, int(dmg * 0.6) - 2)
    if getattr(s, 'yrden_turns', 0) > 0:
        dmg = int(dmg * 0.7)
    if player_action == "axii":
        if random.random() < 0.5:
            s._axii_last_success = True
            return 0
    if player_action == "amulet" and c.enemy == "Морозница":
        dmg = 0
    trait = (c.trait or "").strip()
    if trait == "double_strike":
        total = 0
        for _ in range(2):
            if random.random() < 0.7:
                part = random.randint(max(1, c.dmg_min//2), c.dmg_max)
                part = int(round(part * 1.35))
                total += part
        dmg = max(dmg, total)
    if trait == "burn_items":
        if random.random() < 0.25:
            inv_norm = [norm(x) for x in s.inventory]
            if "зелье" in inv_norm:
                s.inventory = [x for x in s.inventory if norm(x) != "зелье"]
                s._burned_item_last = "зелье"
            elif "травы" in inv_norm:
                s.inventory = [x for x in s.inventory if norm(x) != "травы"]
                s._burned_item_last = "травы"
    if trait == "poison" and dmg > 0:
        if not hasattr(s, "poison_turns") or s.poison_turns <= 0:
            s.poison_turns = 3
    if potion_used:
        dmg //= 2
    if have(s, "амулет") and dmg > 0:
        dmg = max(0, dmg - 2)
    return dmg

# === RENDER LOCATION ===
async def show_location(chat_id: int, s: Session, loc_key: str):
    s.location = loc_key
    node = NODES[loc_key]

    # мгновенные эффекты (штраф hp)
    if "hp_delta" in node:
        s.hp += node["hp_delta"]
        s.hp = max(0, s.hp)

    # бой?
    if "combat" in node and isinstance(node["combat"], Combat):
        # старт боя
        c = node["combat"]
        # создаём новую копию, чтобы не шарить один Combat на всех
        s.combat = Combat(**asdict(c))
        # адаптив: если у героя мало жизней, ослабим врага на 20%
        if s.hp <= 3:
            s.combat.max_hp = int(s.combat.max_hp * 0.8)
            s.combat.hp = s.combat.max_hp
        caption, markup, img = build_combat_message(s)
        await send_photo(chat_id, img, caption, markup)
        return

    # обычная локация
    text = node["text"]
    buttons_rows = []
    for row in node.get("buttons", []):
        row_btns = []
        for b in row:
            if "to" in b:
                row_btns.append({"text": b["text"], "data": f"go:{b['to']}"})
            elif "data" in b:
                row_btns.append({"text": b["text"], "data": b["data"]})
            elif "hint" in b:
                row_btns.append({"text": b["text"], "data": f"hint:{loc_key}"})
        buttons_rows.append(row_btns)

    await send_photo(chat_id, node["img"], text, kb(buttons_rows) if buttons_rows else None)

# === ENDPOINTS ===
@app.get("/")
def ok():
    return {"status": "ok"}

@app.on_event("startup")
async def _set_webhook():
    # Автоустановка вебхука при старте
    if WEBHOOK_BASE:
        await tg("setWebhook", {"url": f"{WEBHOOK_BASE}/webhook/{WEBHOOK_SECRET}"})

@app.post(f"/webhook/{WEBHOOK_SECRET}")
async def webhook(request: Request):
    try:
        upd = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json")

    # messages
    msg = upd.get("message")
    if msg and "text" in msg:
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "")
        t = norm(text)

        # команды
        if t.startswith("/start"):
            SESS[chat_id] = Session()
            intro = (
                "Коловрат — ведьмак Древней Руси. Его призвали в северный уезд: ночью в лесу шепчут огоньки, "
                "в деревне пропадают люди, на болоте воет Волколак, а в каменных кругах стынет Морозница. "
                "Коловоротный амулет обещает дорогу к алтарю, где скрыта причина беды. "
                "Тебя ждут 20 локаций, бои и загадки. Управление *кнопками*. Удачи!\n"
            )
            await send_photo(chat_id, IMG["village"], intro)
            await show_location(chat_id, SESS[chat_id], "intro")
            return {"ok": True}

        if t in ("/жизни", "/hp"):
            s = sget(chat_id)
            await send_text(chat_id, f"❤ Твои жизни: {s.hp}/{s.max_hp}  [{hp_bar(s.hp, s.max_hp)}]")
            return {"ok": True}

        if t in ("/инвентарь", "/inv"):
            s = sget(chat_id)
            inv = ", ".join(s.inventory) if s.inventory else "пусто"
            markup = None
            if s.combat:
                markup = kb([[{"text": "↩ Вернуться в бой", "data": "fight:status"}]])
            await send_text(chat_id, f"🎒 Инвентарь: {inv}", markup)
            return {"ok": True}

        if t in ("/помощь", "/help"):
            await send_text(chat_id, "Игра кнопками. Подсказки скрыты и появляются по кнопке «Подсказка». "
                                     "Команды: /жизни /инвентарь /сброс /помощь.")
            return {"ok": True}

        if t in ("/сброс", "/reset"):
            SESS[chat_id] = Session()
            await send_text(chat_id, "Прогресс сброшен.")
            await show_location(chat_id, SESS[chat_id], "intro")
            return {"ok": True}

        await send_text(chat_id, "Используй *кнопки* ниже. Команды: /жизни /инвентарь /сброс /помощь.")
        return {"ok": True}

    # callbacks (кнопки)
    cq = upd.get("callback_query")
    if cq:
        data = cq.get("data", "")
        chat_id = cq["message"]["chat"]["id"]
        # acknowledge
        try:
            await tg("answerCallbackQuery", {"callback_query_id": cq["id"]})
        except Exception:
            pass

        s = sget(chat_id)

        # hints
        if data.startswith("hint:"):
            _, key = data.split(":", 1)
            if key == "combat" and s.combat:
                await send_text(chat_id, f"💡 Подсказка (бой): {s.combat.hint}")
            else:
                node = NODES.get(key)
                hint = None
                if node:
                    for row in node.get("buttons", []):
                        for b in row:
                            if "hint" in b:
                                hint = b["hint"]
                                break
                    if hint:
                        await send_text(chat_id, f"💡 Подсказка: {hint}")
                    else:
                        await send_text(chat_id, "Подсказка недоступна здесь.")
            return {"ok": True}

        # go:<loc>
        if data.startswith("go:"):
            _, to = data.split(":", 1)
            await show_location(chat_id, s, to)
            return {"ok": True}

        # take:<item>:<next>
        if data.startswith("take:"):
            _, item, nxt = data.split(":", 2)
            add_item(s, item)
            await send_text(chat_id, f"Ты получил: *{item}*.")
            await show_location(chat_id, s, nxt)
            return {"ok": True}

        # brew:<item>:<next>
        if data.startswith("brew:"):
            _, item, nxt = data.split(":", 2)
            if item == "зелье":
                if have(s, "травы"):
                    add_item(s, "зелье")
                    s.inventory = [x for x in s.inventory if norm(x) != "травы"]
                    await send_text(chat_id, "Ты сварил *зелье*.")
                else:
                    await send_text(chat_id, "Нет трав — зелье не сварить.")
            await show_location(chat_id, s, nxt)
            return {"ok": True}

        # fight:<action>
        if data.startswith("fight:"):
            if not s.combat:
                await send_text(chat_id, "Сейчас не бой.")
                return {"ok": True}

            action = data.split(":", 1)[1]  # hit/igni/aard/potion/amulet/... 
            c = s.combat
            if action == "status":
                caption, markup, img = build_combat_message(s)
                await send_photo(chat_id, img, caption, markup)
                return {"ok": True}

            if action == "status":
                caption, markup, img = build_combat_message(s)
                await send_photo(chat_id, img, caption, markup)
                return {"ok": True}

            if action == "yrden":
                s.yrden_turns = 2

            # было ли зелье ДО расхода
            potion_used = (action == "potion") and have(s, "зелье")

            # урон игрока
            pdmg = 0
            if action in ("hit", "igni", "aard", "amulet"):
                pdmg = calc_player_damage(action, s, c)
                c.hp -= pdmg
                c.hp = max(0, c.hp)

            # победа до ответа врага
            if c.hp <= 0:
                await send_text(chat_id, f"🏆 {c.enemy} повержен!")
                s.combat = None
                await show_location(chat_id, s, c.win_to)
                return {"ok": True}

            # урон врага (с учётом, что зелье выпито именно в этот ход)
            edmg = calc_enemy_damage(s, c, action, potion_used)
            fate_saved = False
            if s.hp - edmg <= 0 and s.fate > 0:
                edmg = max(0, s.hp - 1)
                s.fate -= 1
                fate_saved = True

            s.hp -= edmg
            s.hp = max(0, s.hp)
            if (c.trait or "").strip() == "lifesteal" and edmg > 0:
                heal = max(1, edmg // 3)
                c.hp = min(c.max_hp, c.hp + heal)

            # теперь тратим зелье (после применения эффекта и корректного лога)
            if potion_used:
                s.inventory = [x for x in s.inventory if norm(x) != "зелье"]

            # боевой лог и вывод
            caption, markup, img = build_combat_message(s)
            log = []
            if action == "potion":
                if potion_used:
                    log.append("Ты *выпил зелье* — урон в этот ход снижен.")
                else:
                    log.append("Ты пытался выпить зелье, но его нет.")
            elif action == "amulet":
                log.append("Ты показал *амулет*.")
            elif action == "hit":
                log.append(f"Ты ударил: −{pdmg} HP у врага.")
            elif action == "igni":
                log.append(f"Применён *Игни*: −{pdmg} HP у врага.")
            elif action == "aard":
                log.append(f"Порыв *Аарда*: −{pdmg} HP у врага.")
            elif action == "quen":
                log.append("*Квен*: щит смягчит удар в этот ход.")
            elif action == "yrden":
                log.append("*Ирден*: враг ослаблен на 2 хода.")
            elif action == "axii":
                if hasattr(s, "_axii_last_success") and s._axii_last_success:
                    log.append("*Аксий*: враг ошеломлён и пропускает ход!")
                else:
                    log.append("*Аксий*: не сработал.")

            if edmg > 0:
                log.append(f"{c.enemy} бьёт по тебе: −{edmg} HP.")
            else:
                log.append(f"{c.enemy} не смог причинить вреда в этот ход.")
            if hasattr(s, "_burned_item_last") and s._burned_item_last:
                log.append(f"Огонь врага сжёг *{s._burned_item_last}* из твоего инвентаря!")
            if mirror_saved:
                log.append("✨ Осколок зеркала вспыхнул и спас тебя от гибели!")
            elif fate_saved:
                log.append("⚖️ Судьба уберегла тебя от гибели (осталась 1 жизнь).")
            if hasattr(s, "yrden_turns") and s.yrden_turns > 0 and action != "yrden":
                s.yrden_turns -= 1

            # тик яда в конце хода
            if hasattr(s, "poison_turns") and s.poison_turns > 0:
                s.hp = max(0, s.hp - 1)
                s.poison_turns -= 1
                log.append("☠️ Яд гложет тебя: −1 HP.")

            await send_photo(chat_id, img, caption + "\n\n" + "\n".join(log), markup)

            # поражение?
            if s.hp <= 0:
                s.finished = True
                await send_text(chat_id, "💀 Жизни закончились. Нажми «Начать заново».")
                s.combat = None
                await show_location(chat_id, s, "finale")
            return {"ok": True}

        # неизвестная кнопка
        await send_text(chat_id, "Неизвестное действие.")
        return {"ok": True}

    return {"ok": True}
