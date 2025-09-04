
# Коловрат — Telegram-квест на Render (Web Service + webhook)

Бот на aiogram (v2) с кнопками, ветвлениями, пазлами, длинными боями и полосками HP. Работает через webhook на бесплатном Web Service в Render.

## Быстрый деплой на Render
1. Создай новый приватный репозиторий на GitHub и залей туда файлы из этой папки.
2. На https://render.com → **New** → **Web Service**.
3. Подключи репозиторий. План — Free.
4. **Build Command:** `pip install -r requirements.txt`
5. **Start Command:** `python main.py`
6. Переменные окружения (Settings → Environment):
   - `BOT_TOKEN` — токен твоего Telegram-бота
   - `WEBHOOK_SECRET` — любое случайное значение (например, Render сгенерирует автоматически)
   - `WEBHOOK_BASE` — публичный URL сервиса в Render (например: `https://kolovrat-tg-bot.onrender.com`)
7. Нажми **Deploy**. На старте бот вызовет `setWebhook` на `WEBHOOK_BASE/WEBHOOK_SECRET`.
8. Проверь **Logs** — там должна появиться строка о выставлении вебхука.

> Healthcheck: `GET /healthz` возвращает `ok`

## Что внутри
- `game_data.py` — локации/ветки/пазлы/монстры/предметы и простой автребаланс (без «невозможных» боёв).
- `main.py` — логика бота, inline-клавиатуры, бои, подсказки, webhook-сервер на `aiohttp.web`.
- `requirements.txt` — зависимости (aiogram 2.25.1).

## Локально (для отладки)
- Можно запустить: `BOT_TOKEN=... WEBHOOK_BASE=http://localhost:10000 WEBHOOK_SECRET=dev python main.py`
- В таком случае нужен публичный туннель (например, ngrok) на `localhost:10000` и `WEBHOOK_BASE` с этим адресом.

## Кастомизация
- Сцены/баланс — редактируй `game_data.py` (структура похожа на JSON).
- Начальные параметры героя — `BASE_PLAYER`.
- Полоска HP рендерится текстом (▰▱), поэтому красиво выглядит прямо в чате.

## FAQ
**Почему Web Service, а не Background Worker?**  
Для Telegram webhook нужен публичный URL. Web Service идеально подходит, слушает `$PORT` и принимает апдейты.

**Нужно ли ставить uvicorn/FastAPI?**  
Нет. Используем встроенный aiohttp-сервер aiogram (`web.run_app`).

**Если Render спит на Free-плане?**  
Первые секунды бот может просыпаться; Telegram доставит апдейт повторно. При активном использовании сервис бодрствует.
