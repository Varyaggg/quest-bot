
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import random

def rnd(a,b): return random.randint(a,b)
def clamp(v,a,b): return max(a,min(b,v))

MONSTERS = {
  "волкодлак": { "name": "Волкодлак", "baseHp": 40, "dmg": (6,10) },
  "морозница": { "name": "Морозница", "baseHp": 55, "dmg": (5,9) },
  "леший":     { "name": "Леший", "baseHp": 35, "dmg": (4,8) },
  "упырь":     { "name": "Упырь", "baseHp": 28, "dmg": (3,7) },
  "мати-русалка": { "name": "Мати-Русалка", "baseHp": 32, "dmg": (4,8) },
  "чернокнижник": { "name": "Чернокнижник", "baseHp": 60, "dmg": (6,11) },
  "полоз":       { "name": "Полоз", "baseHp": 30, "dmg": (3,7) },
  "ворожей":     { "name": "Ворожей", "baseHp": 36, "dmg": (4,8) }
}

ITEMS = {
  "лекарская трава": { "type": "heal", "amount": 20 },
  "жар-птицы перо":  { "type": "buff", "amount": 3 },
  "оберег от сглаза":{ "type": "def",  "amount": 2 },
  "коловорот":       { "type": "quest" },
  "клык волкодлака": { "type": "quest" },
  "камень лады":     { "type": "quest" },
  "руна мороза":     { "type": "rune" },
  "руна света":      { "type": "rune" },
  "руна крови":      { "type": "rune" }
}

SCENES: Dict[str, Dict[str, Any]] = {
  "start": {
    "title": "Северный уезд",
    "type": "story",
    "text": ("Коловрат — ведьмак Древней Руси. Его призвали в северный уезд: ночью в лесу шепчут огоньки, "
             "в деревне пропадают люди, на болоте воет Волкодлак, а в каменных кругах стынет Морозница. "
             "Коловоротный амулет старцев обещает дорогу к алтарю, где скрыта причина беды. Пройди двадцать испытаний — "
             "тропы, избы, курганы, святилища и пещеры — сразись с нечистью, разгадай руны и собери ключи. На алтаре завершится круг — и зло падёт."),
    "choices": [
      { "t": "Идти к шепчущим огонькам в лес", "to": "forest-lights" },
      { "t": "Спросить травницу на окраине", "to": "herbalist-hut" },
      { "t": "Проверить старый мост через омут", "to": "old-bridge" }
    ],
    "hint": "Сначала неплохо бы разжиться лечением и оберегами."
  },
  "forest-lights": {
    "title": "Лес у капища",
    "type": "puzzle",
    "text": "Между сосен мерцают блуждающие огни. На корнях вырезаны три руны: ᚠ, ᚷ, ᛚ.",
    "puzzle": {
      "q": "Какая руна означает помощь путнику?",
      "opts": [
        {"t":"ᚠ (богатство)", "ok": False},
        {"t":"ᚷ (дар)", "ok": True},
        {"t":"ᛚ (вода)", "ok": False}
      ],
      "succ": "gift-clearing",
      "fail": "bog-edge"
    },
    "hint": "Дар ведёт к дарам — ищи 'ᚷ'."
  },
  "gift-clearing": {
    "title": "Поляна даров",
    "type": "story",
    "text": "Огни выстраиваются в круг. На пне лежат зелья и обереги.",
    "onEnterGive": ["лекарская трава", "оберег от сглаза"],
    "choices": [
      {"t":"Дальше в чащу", "to":"leshy-grove"},
      {"t":"Вернуться", "to":"start"}
    ]
  },
  "bog-edge": {
    "title": "Край болота",
    "type": "story",
    "text": "Ступишь неверно — утонешь. Вдалеке вой Волкодлака.",
    "choices": [
      {"t":"Ступить на кочку и привлечь тварь", "to":"fight-wolf"},
      {"t":"Отступить к чаще", "to":"leshy-grove"}
    ]
  },
  "leshy-grove": {
    "title": "Чаща Лешего",
    "type": "combat",
    "text": "В тишине трещит сухая ветка — Леший недоволен чужаком.",
    "combat": {"enemies": [{"kind":"леший"}]},
    "afterWin": "stone-circles", "afterLose":"game-over"
  },
  "stone-circles": {
    "title": "Каменные круги",
    "type": "story",
    "text": "Холодом тянет от камней. Ветер складывает снег в знаки Морозницы.",
    "choices": [
      {"t":"Приложить Коловоротный амулет", "to":"frost-puzzle", "need":{"item":"коловорот"}},
      {"t":"Осмотреть тропу к болоту", "to":"bog-edge"},
      {"t":"Идти к святилищу в пещере", "to":"cave-shrine"}
    ],
    "hint":"Амулет старцев пригодится позже — поищи у людей."
  },
  "herbalist-hut": {
    "title": "Изба травницы",
    "type": "story",
    "text": "Знахарка шепчет: 'Собери три руны — мороз, свет и кровь. Ищи Коловорот у кузнеца, клык у Волкодлака, камень у Морозницы.'",
    "onEnterGive": ["лекарская трава"],
    "choices": [
      {"t":"Взять задание и карту троп", "to":"map-choice"},
      {"t":"Спросить про обряды", "to":"rituals"}
    ]
  },
  "rituals": {
    "title": "Обряды и знаки",
    "type": "story",
    "text": "Перун — парирование на удар. Дар Огня — усиление следующего удара (перо).",
    "choices": [
      {"t":"Вернуться к избе", "to":"herbalist-hut"},
      {"t":"К кузнице", "to":"old-smithy"}
    ]
  },
  "map-choice": {
    "title": "Развилка троп",
    "type": "story",
    "text": "Куда держать путь?",
    "choices": [
      {"t":"К болоту Волкодлака", "to":"fight-wolf"},
      {"t":"К старой кузне", "to":"old-smithy"},
      {"t":"К пещере святилища", "to":"cave-shrine"}
    ]
  },
  "old-smithy": {
    "title": "Забытая кузня",
    "type": "puzzle",
    "text": "Кузнец оставил загадку: 'Что крепче стали — но тает от слова?'",
    "puzzle": {
      "q": "Ответ найдёшь на наковальне...",
      "opts":[
        {"t":"Лёд", "ok": True},
        {"t":"Камень", "ok": False},
        {"t":"Кожа", "ok": False}
      ],
      "succ":"smithy-reward",
      "fail":"smithy-guard"
    },
    "hint":"Слово — это тепло."
  },
  "smithy-reward": {
    "title": "Дар кузнеца",
    "type": "story",
    "text": "Под плитой — Коловоротный амулет и перо Жар-Птицы.",
    "onEnterGive": ["коловорот","жар-птицы перо"],
    "choices":[
      {"t":"Назад к развилке", "to":"map-choice"},
      {"t":"К каменным кругам", "to":"stone-circles"}
    ]
  },
  "smithy-guard": {
    "title": "Страж у горна",
    "type": "combat",
    "text": "Из золы поднимается Упырь.",
    "combat":{"enemies":[{"kind":"упырь"}]},
    "afterWin":"smithy-reward","afterLose":"game-over"
  },
  "old-bridge": {
    "title": "Старый мост",
    "type": "story",
    "text": "Под мостом шепчет омут — русалки ищут жертву.",
    "choices":[
      {"t":"Перебежать быстро", "to":"mill-hill"},
      {"t":"Спуститься к воде", "to":"rusalka-fight"}
    ]
  },
  "rusalka-fight": {
    "title": "Омут русалки",
    "type": "combat",
    "text": "Холодные руки тянутся из воды.",
    "combat":{"enemies":[{"kind":"мати-русалка"},{"kind":"полоз"}]},
    "afterWin":"rusalka-loot","afterLose":"game-over"
  },
  "rusalka-loot": {
    "title": "Берег находок",
    "type": "story",
    "text": "В водорослях — оберег и лечебная трава.",
    "onEnterGive":["оберег от сглаза","лекарская трава"],
    "choices":[{"t":"К мельнице", "to":"mill-hill"}]
  },
  "mill-hill": {
    "title": "Старая мельница",
    "type": "story",
    "text": "Крылья стоят. Внутри — тайник с руной света.",
    "onEnterGive":["руна света"],
    "choices":[
      {"t":"Вернуться к мосту", "to":"old-bridge"},
      {"t":"К каменным кругам", "to":"stone-circles"}
    ]
  },
  "fight-wolf": {
    "title": "Трясина Волкодлака",
    "type": "combat",
    "text": "Из тумана выходит Волкодлак.",
    "combat":{"enemies":[{"kind":"волкодлак"}]},
    "afterWin":"wolf-loot","afterLose":"game-over"
  },
  "wolf-loot": {
    "title": "Клык на мокрой кочке",
    "type": "story",
    "text": "Побеждённый Волкодлак оставил клык.",
    "onEnterGive":["клык волкодлака"],
    "choices":[
      {"t":"К каменным кругам", "to":"stone-circles"},
      {"t":"В пещеру святилища", "to":"cave-shrine"}
    ]
  },
  "cave-shrine": {
    "title": "Пещера святилища",
    "type": "puzzle",
    "text": "На алтарной плите три углубления под руны. Надпись: 'Мороз удержит зло, Свет прольёт истину, Кровь завершит круг.'",
    "puzzle":{
      "q":"Какие две руны положить сначала?",
      "opts":[
        {"t":"Мороз и Свет", "ok": True},
        {"t":"Кровь и Свет", "ok": False},
        {"t":"Мороз и Кровь", "ok": False}
      ],
      "succ":"ice-spirit","fail":"shadow-ambush"
    },
    "hint":"Лёд прежде крови."
  },
  "shadow-ambush":{
    "title":"Засада теней",
    "type":"combat",
    "text":"Из щелей вырываются тени.",
    "combat":{"enemies":[{"kind":"упырь"},{"kind":"ворожей"}]},
    "afterWin":"ice-spirit","afterLose":"game-over"
  },
  "ice-spirit":{
    "title":"Обитель Морозницы",
    "type":"combat",
    "text":"Морозница встаёт во льду, холод режет лёгкие.",
    "combat":{"enemies":[{"kind":"морозница"}]},
    "afterWin":"frost-loot","afterLose":"game-over"
  },
  "frost-loot":{
    "title":"Камень Лады",
    "type":"story",
    "text":"Во льду мерцает голубой камень — последний ключ.",
    "onEnterGive":["камень лады","руна мороза"],
    "choices":[
      {"t":"К каменным кругам", "to":"stone-circles"},
      {"t":"К алтарю развязки", "to":"final-altar", "need":{"runeCount":2}}
    ]
  },
  "frost-puzzle":{
    "title":"Ключ от круга",
    "type":"puzzle",
    "text":"Камни гудят. Коловорот открывает путь — но надо выбрать верную строку заклятья.",
    "puzzle":{
      "q":"Какую строку произнести?",
      "opts":[
        {"t":"Кровь по снегу — тьма к порогу", "ok": False},
        {"t":"Свет по кругу — стужу в дугу", "ok": True},
        {"t":"Гром по лесу — ночь исчезу", "ok": False}
      ],
      "succ":"final-altar","fail":"shadow-ambush"
    }
  },
  "final-altar":{
    "title":"Алтарь развязки",
    "type":"story",
    "text":"Алтарь ждёт ключи. Круг завершится — зло падёт.",
    "choices":[
      {"t":"Совершить обряд и завершить круг", "to":"ending", "need":{"item":"коловорот"}},
      {"t":"Вернуться и усилиться ещё", "to":"map-choice"}
    ],
    "hint":"Клык Волкодлака и Камень Лады пригодятся."
  },
  "ending":{
    "title":"Завершение круга",
    "type":"story",
    "text":"Ты кладёшь ключи. Руны вспыхивают. Морозница тает, волчий вой стихает. Северный уезд спасён.",
    "onEnterGive":["руна крови"],
    "choices":[{"t":"Начать заново (Новая история)","to":"start"}]
  },
  "game-over":{
    "title":"Падение героя",
    "type":"story",
    "text":"Ты пал в бою. Но дорога зовёт снова...",
    "choices":[{"t":"Попробовать ещё раз","to":"start"}]
  }
}

BASE_PLAYER = {"maxHp":60, "hp":60, "atk":[5,9], "def":1, "fate":1}

def safe_fight_plan(player, enemies):
    p_avg = sum(player["atk"])/2
    total_hp = sum(MONSTERS[e["kind"]]["baseHp"] for e in enemies)
    rounds_to_kill = max(1, int((total_hp + p_avg - 1) // p_avg))
    e_avg = sum(sum(MONSTERS[e["kind"]]["dmg"])/2 for e in enemies)
    expected_incoming = int(rounds_to_kill * (e_avg*0.6))
    buffer = 40
    return "ok" if expected_incoming <= player["hp"] + buffer else "tooHard"

def hp_bar(cur, mx, width=12):
    if mx<=0: return ""
    filled = int(width * max(0, cur) / mx + 0.5)
    filled = min(width, filled)
    return "▰"*filled + "▱"*(width-filled)
