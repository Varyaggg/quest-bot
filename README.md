[README.md](https://github.com/user-attachments/files/22144887/README.md)

# Коловрат FastAPI Bot — фикс боёвки + Render

## Что изменили
- Правильная обработка зелья (−50% урона в ход применения).
- «Судьба» спасает один раз от летального удара.
- Адаптив: если у героя ≤3 жизни — HP врага −20% на старте боя.
- Баланс урона врагов под 8 жизней: Леший (1–3), Туманник (1–2), Морозница (2–3), Волколак (2–4), Змей (2–3).
- Авто-выставление вебхука на `{WEBHOOK_BASE}/webhook/{WEBHOOK_SECRET}` при старте.
- Для Render: `Start Command = uvicorn main:app --host 0.0.0.0 --port $PORT`.

## Деплой на Render
1. Залей в репозиторий эти файлы.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Env:
   - BOT_TOKEN = токен из BotFather
   - WEBHOOK_SECRET = любая строка (напр. mysecret123)
   - WEBHOOK_BASE = Public URL сервиса (после деплоя вида https://<имя>.onrender.com)
