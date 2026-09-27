# SHAMA WORLD — Clean Render Build

Это чистая сборка Telegram Mini App без `uvicorn routes:app`, без относительных импортов и без зависимости от отдельного web-сервера.

## Структура

```text
bot.py
config.py
database.py
routes.py
requirements.txt
render.yaml
web/
  index.html
  assets/
    world-city.svg
```

## Render

Build:
`pip install -r requirements.txt`

Start:
`python bot.py`

Environment:
`BOT_TOKEN=...`

После первого запуска Render даст `RENDER_EXTERNAL_URL`. Бот автоматически использует:
`RENDER_EXTERNAL_URL/app`

## GitHub

Загружай всю структуру как есть. Папка `web` должна находиться в корне репозитория.

## Важно

В GitHub не хранить BOT_TOKEN.

## Лимит GitHub

В этой сборке нет сотен отдельных картинок/файлов: игровой интерфейс использует CSS, SVG и один набор серверных файлов. Поэтому лимит на большое количество мелких assets не должен быть проблемой.
