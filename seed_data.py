"""Idempotent starter content for the first cases release."""

from __future__ import annotations

from typing import Any
from datetime import datetime, timedelta, timezone

try:
    from database import get_connection, init_db
except ImportError:  # pragma: no cover
    from .database import get_connection, init_db


ITEMS: list[dict[str, Any]] = [
    {"name": "Neon Token", "description": "Первый знак удачи в SHAMA WORLD.", "rarity": "COMMON", "value": 40, "image": "/assets/items/neon-token.svg"},
    {"name": "City Sticker", "description": "Стикер ночного города для твоей коллекции.", "rarity": "COMMON", "value": 55, "image": "/assets/items/city-sticker.svg"},
    {"name": "Chrome Key", "description": "Холодный хром и обещание новых дверей.", "rarity": "COMMON", "value": 65, "image": "/assets/items/chrome-key.svg"},
    {"name": "Pulse Badge", "description": "Пропуск в ритм большого города.", "rarity": "COMMON", "value": 75, "image": "/assets/items/pulse-badge.svg"},
    {"name": "Night Pass", "description": "Билет на ночную сторону SHAMA.", "rarity": "COMMON", "value": 90, "image": "/assets/items/night-pass.svg"},
    {"name": "Violet Chip", "description": "Фиолетовый чип с редким свечением.", "rarity": "UNCOMMON", "value": 120, "image": "/assets/items/violet-chip.svg"},
    {"name": "Street Lens", "description": "Линза, которая видит больше обычного.", "rarity": "UNCOMMON", "value": 145, "image": "/assets/items/street-lens.jpg"},
    {"name": "Orbit Ring", "description": "Маленькая орбита для большой истории.", "rarity": "UNCOMMON", "value": 180, "image": "/assets/items/orbit-ring.svg"},
    {"name": "Signal Deck", "description": "Колода сигналов из скрытых районов.", "rarity": "UNCOMMON", "value": 220, "image": "/assets/items/signal-deck.svg"},
    {"name": "Shama Tag", "description": "Знак тех, кто знает путь в мир.", "rarity": "UNCOMMON", "value": 260, "image": "/assets/items/shama-tag.jpg"},
    {"name": "Torpedo Ball", "description": "Мяч команды TORPEDO для решающего удара.", "rarity": "RARE", "value": 500, "image": "/assets/items/torpedo-ball.jpg"},
    {"name": "Torpedo Scarf", "description": "Шарф с цветами трибун TORPEDO.", "rarity": "RARE", "value": 650, "image": "/assets/items/torpedo-scarf.jpg"},
    {"name": "Torpedo Boots", "description": "Бутсы для тех, кто ускоряет игру.", "rarity": "RARE", "value": 800, "image": "/assets/items/torpedo-boots.jpg"},
    {"name": "Torpedo Jersey", "description": "Игровая форма легендарного сезона.", "rarity": "EPIC", "value": 1200, "image": "/assets/items/torpedo-jersey.svg"},
    {"name": "Torpedo Trophy", "description": "Трофей, который помнит каждый финал.", "rarity": "LEGENDARY", "value": 2400, "image": "/assets/market/torpedo-trophy.jpg"},
    {"name": "Shama Prism", "description": "Призма с энергией центральной площади.", "rarity": "RARE", "value": 700, "image": "/assets/items/shama-prism.svg"},
    {"name": "Midnight Radio", "description": "Радио с голосами из другого измерения.", "rarity": "EPIC", "value": 1500, "image": "/assets/items/midnight-radio.svg"},
    {"name": "Ghost Jacket", "description": "Куртка, растворяющаяся в неоновом свете.", "rarity": "EPIC", "value": 1800, "image": "/assets/items/ghost-jacket.svg"},
    {"name": "Royal Visor", "description": "Визор для тех, кто видит карту целиком.", "rarity": "LEGENDARY", "value": 3200, "image": "/assets/items/royal-visor.jpg"},
    {"name": "Void Compass", "description": "Компас, указывающий на неизвестное.", "rarity": "MYTHIC", "value": 6000, "image": "/assets/items/void-compass.svg"},
    {"name": "Solar Core", "description": "Сердце, собранное из солнечного импульса.", "rarity": "MYTHIC", "value": 7500, "image": "/assets/items/solar-core.jpg"},
    {"name": "Shadow Mask", "description": "Маска для тихих маршрутов SHAMA.", "rarity": "RARE", "value": 900, "image": "/assets/items/shadow-mask.jpg"},
    {"name": "Obsidian Blade", "description": "Черное лезвие с мягким фиолетовым бликом.", "rarity": "EPIC", "value": 2100, "image": "/assets/items/obsidian-blade.svg"},
    {"name": "Crown of Echoes", "description": "Корона тех, чьи истории не забывают.", "rarity": "LEGENDARY", "value": 4500, "image": "/assets/items/crown-of-echoes.jpg"},
    {"name": "World Seed", "description": "Мифическое зерно будущего мира.", "rarity": "MYTHIC", "value": 10000, "image": "/assets/items/world-seed.svg"},
]


# V7 collection: physical-looking collectible assets with clear rarity progression.
V7_ITEMS: list[dict[str, Any]] = [
    {"name":"Gold Bar","description":"Тяжёлый слиток чистого золота из банковского хранилища SHAMA.","rarity":"RARE","value":900,"image":"/assets/items/gold-bar.jpg"},
    {"name":"Silver Bar","description":"Серебряный слиток — базовый драгоценный металл коллекции.","rarity":"UNCOMMON","value":300,"image":"/assets/items/silver-bar.jpg"},
    {"name":"Bronze Bar","description":"Бронзовый слиток для первых коллекционных наборов.","rarity":"COMMON","value":120,"image":"/assets/items/bronze-bar.jpg"},
    {"name":"Gold Medal","description":"Золотая медаль за чемпионский сезон.","rarity":"EPIC","value":1800,"image":"/assets/items/gold-medal.jpg"},
    {"name":"Silver Medal","description":"Серебряная медаль призёра.","rarity":"RARE","value":850,"image":"/assets/items/silver-medal.jpg"},
    {"name":"Bronze Medal","description":"Бронзовая медаль за третье место.","rarity":"UNCOMMON","value":420,"image":"/assets/items/bronze-medal.jpg"},
    {"name":"Torpedo Cup","description":"Главный футбольный трофей TORPEDO STADIUM.","rarity":"LEGENDARY","value":4200,"image":"/assets/items/torpedo-cup.jpg"},
    {"name":"Football","description":"Коллекционный футбольный мяч SHAMA WORLD.","rarity":"RARE","value":650,"image":"/assets/items/football.jpg"},
    {"name":"HP Energy","description":"Редкий энергетический ресурс для игровых механик.","rarity":"EPIC","value":1400,"image":"/assets/items/hp-energy.jpg"},
    {"name":"SH Coins","description":"Коллекционная пачка монет SH.","rarity":"COMMON","value":80,"image":"/assets/items/sh-coins.jpg"},
    {"name":"City Compact","description":"Начальный городской автомобиль.","rarity":"COMMON","value":500,"image":"/assets/items/car-basic.jpg"},
    {"name":"Sport Coupe","description":"Быстрый городской спорткар.","rarity":"RARE","value":1500,"image":"/assets/items/car-sport.jpg"},
    {"name":"Luxury Sedan","description":"Премиальный седан для высокого уровня.","rarity":"EPIC","value":3500,"image":"/assets/items/car-luxury.jpg"},
    {"name":"Supercar","description":"Эксклюзивный суперкар SHAMA WORLD.","rarity":"LEGENDARY","value":8000,"image":"/assets/items/car-super.jpg"},
    {"name":"Hypercar","description":"Самая редкая автомобильная серия города.","rarity":"MYTHIC","value":18000,"image":"/assets/items/car-hyper.jpg"},
    {"name":"City House","description":"Первый собственный дом в SHAMA WORLD.","rarity":"COMMON","value":900,"image":"/assets/items/house-basic.jpg"},
    {"name":"Comfort Home","description":"Улучшенный городской дом.","rarity":"UNCOMMON","value":2200,"image":"/assets/items/house-comfort.jpg"},
    {"name":"City Villa","description":"Просторная вилла высокого уровня.","rarity":"EPIC","value":6000,"image":"/assets/items/house-villa.jpg"},
    {"name":"SH Mansion","description":"Большой особняк для самых богатых игроков.","rarity":"LEGENDARY","value":14000,"image":"/assets/items/house-mansion.jpg"},
    {"name":"Street Hoodie","description":"Недорогая городская одежда.","rarity":"COMMON","value":180,"image":"/assets/items/hoodie-budget.jpg"},
    {"name":"Premium Hoodie","description":"Премиальный худи ограниченной серии.","rarity":"EPIC","value":1800,"image":"/assets/items/hoodie-premium.jpg"},
    {"name":"Jordan 1","description":"Коллекционная серия JORDAN 1.","rarity":"RARE","value":1600,"image":"/assets/items/jordan-1.jpg"},
    {"name":"Jordan 4","description":"Коллекционная серия JORDAN 4.","rarity":"EPIC","value":3200,"image":"/assets/items/jordan-4.jpg"},
    {"name":"Jordan 11","description":"Премиальная серия JORDAN 11.","rarity":"LEGENDARY","value":6500,"image":"/assets/items/jordan-11.jpg"},
    {"name":"Luxury Watch","description":"Коллекционные часы высшей категории.","rarity":"LEGENDARY","value":9000,"image":"/assets/items/luxury-watch.jpg"},
]

MARKET_ROTATION_NAMES = ("Shama Tag", "Solar Core", "Torpedo Cup", "City Villa", "Torpedo Trophy", "Shadow Mask", "Football", "SH Mansion")

CASES = [
    {"name": "STARTER CASE", "description": "Первый шаг в коллекцию SHAMA WORLD.", "price": 100, "image": "/assets/cases/starter.jpg", "drops": [("Bronze Bar", .45), ("Silver Bar", .30), ("SH Coins", .15), ("Football", .08), ("Bronze Medal", .02)]},
    {"name": "STREET CASE", "description": "Ритм улиц, редкие сигналы и ночной стиль.", "price": 300, "image": "/assets/cases/street.jpg", "drops": [("Street Hoodie", .32), ("Silver Medal", .28), ("Jordan 1", .20), ("Gold Bar", .15), ("Jordan 4", .05)]},
    {"name": "TORPEDO CASE", "description": "Футбольная энергия TORPEDO внутри каждого открытия.", "price": 750, "image": "/assets/cases/torpedo.jpg", "drops": [("Football", .28), ("Torpedo Cup", .03), ("Gold Medal", .18), ("Jordan 1", .25), ("Jordan 4", .26)]},
    {"name": "SHADOW CASE", "description": "Темная серия для охотников за эпическими предметами.", "price": 1500, "image": "/assets/cases/shadow.jpg", "drops": [("Premium Hoodie", .30), ("Sport Coupe", .28), ("Gold Medal", .20), ("Luxury Sedan", .17), ("Jordan 11", .05)]},
    {"name": "LEGEND CASE", "description": "Самые редкие сигналы мира собраны в одном кейсе.", "price": 5000, "image": "/assets/cases/legend.jpg", "drops": [("Supercar", .36), ("City Villa", .26), ("SH Mansion", .16), ("Torpedo Cup", .12), ("Hypercar", .06), ("Luxury Watch", .04)]},
]

PASSIVE_LEVELS = {
    "farm": [(50, 0), (60, 250), (72, 500), (85, 900), (100, 1500), (120, 2400), (145, 3800), (175, 6000), (210, 9000), (250, 13000)],
    "business": [(35, 3000), (45, 4200), (55, 5800), (66, 7800), (78, 10200), (92, 13200), (108, 16800), (126, 21000), (147, 26000), (170, 32000), (190, 39000), (210, 47000), (230, 56000), (250, 66000), (270, 78000), (282, 92000), (290, 108000), (296, 126000), (299, 148000), (300, 175000)],
    "bank": [(60, 12000), (75, 15000), (92, 19000), (110, 24000), (132, 30000), (158, 37000), (188, 45000), (220, 54000), (255, 65000), (295, 78000), (335, 92000), (360, 108000), (385, 126000), (410, 148000), (430, 175000), (450, 205000), (465, 240000), (478, 280000), (490, 325000), (500, 375000), (500, 430000), (500, 490000), (500, 555000), (500, 625000), (500, 700000), (500, 780000), (500, 865000), (500, 955000), (500, 1050000), (500, 1150000)],
}

WORLD_LOCATIONS = [
    ("TORPEDO STADIUM", "stadium", -8, 0, 4, "Футбольное сердце города TORPEDO.", 1, "/assets/world/torpedo-stadium.svg"),
    ("SH MARKET", "market", 5, 0, 2, "Рынок NPC Mac с ротацией предложений.", 1, "/assets/world/sh-market.svg"),
    ("COURIER HUB", "courier", 2, 0, -6, "Склад, машины и маршруты доставки.", 1, "/assets/world/courier-hub.svg"),
    ("CASE FACTORY", "factory", 10, 0, -4, "Завод сборки кейсов.", 5, "/assets/world/case-factory.svg"),
    ("FARM", "farm", -4, 0, -8, "Пассивный источник SH.", 1, "/assets/world/farm.svg"),
    ("BUSINESS", "business", 8, 0, 7, "Следующая ступень пассивной экономики.", 10, "/assets/world/business.svg"),
    ("BANK", "bank", 14, 0, 8, "Поздняя стадия прогрессии.", 20, "/assets/world/bank.svg"),
    ("PLAYER PROFILE AREA", "profile", 0, 0, 8, "Личное пространство игрока.", 1, "/assets/world/profile-area.svg"),
]

ACHIEVEMENTS = [
    ("FIRST_CASE", "FIRST CASE", "Открой первый кейс.", 1, 10),
    ("OPEN_10_CASES", "CASE RUNNER", "Открой 10 кейсов.", 10, 25),
    ("COLLECT_10_ITEMS", "COLLECTOR", "Собери 10 типов предметов.", 10, 30),
    ("UPGRADE_SUCCESS", "RISK TAKER", "Успешно проведи апгрейд.", 1, 15),
    ("SELL_10_ITEMS", "TRADER", "Продай 10 предметов.", 10, 20),
    ("REACH_LEVEL_10", "RISING", "Достигни 10 уровня.", 10, 50),
    ("BANK_CONTROL_PACKAGE", "КОНТРОЛЬНЫЙ ПАКЕТ", "Владей не менее чем половиной акций одной компании.", 1, 0),
]


def seed_content(database_path: str) -> None:
    init_db(database_path)
    with get_connection(database_path) as connection:
        for item in ITEMS:
            connection.execute(
                """INSERT INTO items (name, description, rarity, value, image)
                   VALUES (:name, :description, :rarity, :value, :image)
                   ON CONFLICT(name) DO UPDATE SET description=excluded.description,
                   rarity=excluded.rarity, value=excluded.value, image=excluded.image""",
                item,
            )
        for item in V7_ITEMS:
            connection.execute(
                """INSERT INTO items (name, description, rarity, value, image)
                   VALUES (:name, :description, :rarity, :value, :image)
                   ON CONFLICT(name) DO UPDATE SET description=excluded.description,
                   rarity=excluded.rarity, value=excluded.value, image=excluded.image""",
                item,
            )
        for case in CASES:
            connection.execute(
                """INSERT INTO cases (name, description, price, image)
                   VALUES (:name, :description, :price, :image)
                   ON CONFLICT(name) DO UPDATE SET description=excluded.description,
                   price=excluded.price, image=excluded.image""",
                {key: case[key] for key in ("name", "description", "price", "image")},
            )
        for case in CASES:
            if abs(sum(chance for _, chance in case["drops"]) - 1.0) > 0.00001:
                raise ValueError(f"Drop pool for {case['name']} must sum to 1.0")
            case_id = connection.execute("SELECT id FROM cases WHERE name = ?", (case["name"],)).fetchone()[0]
            # V7 replaces the drop tables rather than leaving obsolete V5/V6 drops behind.
            connection.execute("DELETE FROM case_drops WHERE case_id = ?", (case_id,))
            for item_name, chance in case["drops"]:
                item_id = connection.execute("SELECT id FROM items WHERE name = ?", (item_name,)).fetchone()[0]
                connection.execute(
                    """INSERT INTO case_drops (case_id, item_id, chance) VALUES (?, ?, ?)
                       ON CONFLICT(case_id, item_id) DO UPDATE SET chance=excluded.chance""",
                    (case_id, item_id, chance),
                )
        connection.commit()
    seed_extended_content(database_path)


def seed_extended_content(database_path: str) -> None:
    """Seed non-case systems idempotently."""

    with get_connection(database_path) as connection:
        for system, levels in PASSIVE_LEVELS.items():
            for index, (income, cost) in enumerate(levels, start=1):
                unlock = 1 if system == "farm" else (10 if system == "business" else 20)
                connection.execute(
                    """INSERT INTO passive_levels(system, level, income_per_minute, upgrade_cost, unlock_level)
                       VALUES (?, ?, ?, ?, ?)
                       ON CONFLICT(system, level) DO UPDATE SET income_per_minute=excluded.income_per_minute,
                       upgrade_cost=excluded.upgrade_cost, unlock_level=excluded.unlock_level""",
                    (system, index, income, cost, unlock),
                )
        for location in WORLD_LOCATIONS:
            connection.execute(
                """INSERT INTO world_locations(name, type, position_x, position_y, position_z, description, unlock_level, image)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET type=excluded.type, position_x=excluded.position_x,
                   position_y=excluded.position_y, position_z=excluded.position_z, description=excluded.description,
                   unlock_level=excluded.unlock_level, image=excluded.image""",
                location,
            )
        for achievement in ACHIEVEMENTS:
            connection.execute(
                """INSERT INTO achievements(code, name, description, requirement, reward_xp)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(code) DO UPDATE SET name=excluded.name, description=excluded.description,
                   requirement=excluded.requirement, reward_xp=excluded.reward_xp""",
                achievement,
            )
        connection.commit()
    ensure_market_rotation(database_path)


def ensure_market_rotation(database_path: str) -> None:
    now = datetime.now(timezone.utc)
    with get_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        rotation = connection.execute("SELECT * FROM market_rotations ORDER BY id DESC LIMIT 1").fetchone()
        if rotation and datetime.fromisoformat(rotation["ends_at"]) > now:
            return
        started = now.replace(minute=(now.hour // 4) * 4, second=0, microsecond=0)
        ends = started + timedelta(hours=4)
        cursor = connection.execute("INSERT INTO market_rotations(started_at, ends_at) VALUES (?, ?)", (started.isoformat(), ends.isoformat()))
        rotation_id = cursor.lastrowid
        placeholders = ",".join("?" for _ in MARKET_ROTATION_NAMES)
        offers = connection.execute(
            f"SELECT id, value FROM items WHERE name IN ({placeholders}) ORDER BY CASE name "
            + " ".join(f"WHEN ? THEN {index}" for index in range(len(MARKET_ROTATION_NAMES)))
            + " ELSE 999 END",
            (*MARKET_ROTATION_NAMES, *MARKET_ROTATION_NAMES),
        ).fetchall()
        for index, item in enumerate(offers):
            price = max(100, int(item["value"] * (1.15 + (index % 3) * 0.2)))
            connection.execute("INSERT INTO market_offers(rotation_id, item_id, price, stock) VALUES (?, ?, ?, ?)", (rotation_id, item["id"], price, 1 + (index % 2)))
        connection.commit()


if __name__ == "__main__":
    try:
        from config import get_settings
    except ImportError:
        from .config import get_settings
    seed_content(get_settings(require_bot=False, require_webapp=False).database_path)
