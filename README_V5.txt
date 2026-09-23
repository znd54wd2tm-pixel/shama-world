# SHAMA WORLD v5

Полноценная серверная основа Telegram Mini App.

## Что есть
- Telegram `/start` -> кнопка открытия Mini App.
- Серверный SQLite: баланс, XP, уровни, инвентарь, история, достижения.
- Telegram WebApp initData проверяется сервером.
- Daily bonus с серией входов.
- Игровые паки с гарантированной наградой.
- Анимация открытия.
- Инвентарь.
- Рейтинг.
- Профиль и достижения.
- API на том же Render-сервисе.

## Важное ограничение
CW — виртуальная игровая валюта. В этой версии нет покупки CW за реальные деньги,
ставок, вывода денег или азартной системы вероятностей. Пак содержит гарантированную
награду и используется как элемент прогресса/коллекционирования.

## GitHub
Загрузить/заменить:
bot.py
config.py
database.py
api_server.py
requirements.txt
web/index.html

Папка web должна находиться в корне репозитория:
web/index.html

Не менять BOT_TOKEN вручную в коде. Он должен оставаться в Environment Variables
Render под именем BOT_TOKEN.

После Commit changes дождаться Live.

## Render
Нужен Web Service, а не static site. Start Command:
python bot.py

Render должен предоставить RENDER_EXTERNAL_URL. Если его нет, укажи публичный
URL сервиса как переменную RENDER_EXTERNAL_URL, например:
https://YOUR-SERVICE.onrender.com
