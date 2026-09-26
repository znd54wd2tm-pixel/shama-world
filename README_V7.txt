# SHAMA WORLD V7

V7 — визуальный апгрейд поверх рабочей V6 без замены серверной архитектуры.

## V7 UI
- Вкладка «Мир» больше не использует фотографию как основной интерфейс.
- Добавлена интерактивная изометрическая 3D-like карта города: дороги, кварталы, вода, парки, здания, машины и крупные landmarks.
- Drag/swipe вращает обзор, pinch/wheel меняет масштаб, reset возвращает камеру.
- TORPEDO STADIUM, SH MARKET, CASE FACTORY, COURIER HUB, SHAMA BANK и PLAYER HUB являются кликабельными объектами.
- На мобильном приоритет отдан touch/pointer interactions.

## V7 inventory / upgrade fix
- При переходе из карточки предмета в «Апгрейд» все modal sheets принудительно закрываются.
- Переход в Upgrade теперь ждёт загрузку инвентаря перед выбором исходного предмета, поэтому старое окно предмета не остаётся поверх страницы.
- Modal state очищается при навигации между разделами.

## V7 collection
Добавлена новая полноценная коллекция с rarity progression:
- Gold / Silver / Bronze Bars
- Gold / Silver / Bronze Medals
- Torpedo Cup
- Football
- HP Energy
- SH Coins
- автомобили от City Compact до Hypercar
- дома от City House до SH Mansion
- Street / Premium Hoodies
- Jordan 1 / Jordan 4 / Jordan 11
- Luxury Watch

Новые предметы имеют отдельные визуальные SVG-art assets и реальные значения rarity/value.

## Cases
Пулы дропа пяти кейсов обновлены под V7 коллекцию. Перед записью новых drop pools старые записи case_drops для каждого кейса очищаются, поэтому устаревшие V5/V6 предметы не продолжают выпадать из кейсов.

## Backend
Не изменены Telegram WebApp auth, SQLite, существующие API, серверная авторитетность баланса/XP/шансов, рынок, заработок, продажи и upgrade mechanics.

Upgrade chance по-прежнему рассчитывается сервером в services/upgrade.py. Frontend не передаёт backend шанс, стоимость или результат.
