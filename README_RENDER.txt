SHAMA WORLD — запуск через Render

1. Создай GitHub-репозиторий и загрузи в него ВСЕ файлы из этой папки.
2. В Render создай Web Service из этого GitHub-репозитория.
3. Build Command:
   pip install -r requirements.txt
4. Start Command:
   python bot.py
5. В Environment Variables создай:
   BOT_TOKEN = НОВЫЙ_ТОКЕН_ОТ_BOTFATHER
6. Нажми Deploy.

Код использует Telegram webhook и переменную окружения, поэтому токен не хранится в файлах.

ВАЖНО:
Render Free подходит для теста/прототипа. Бесплатный сервис может иметь ограничения, а локальный SQLite не предназначен для надежного постоянного хранения. Для полноценной версии позже подключим нормальную БД.
