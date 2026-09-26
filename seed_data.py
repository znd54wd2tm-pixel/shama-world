"""Idempotent starter content for the first cases release."""

from __future__ import annotations

from typing import Any
from datetime import datetime, timedelta, timezone

try:
    from database import get_connection, init_db
except ImportError:  # pragma: no cover
    from .database import get_connection, init_db


ITEMS: list[dict[str, Any]] = [
    {"name": "Neon Token", "description": "Первый знак удачи в SHAMA WORLD.", "rarity": "COMMON", "value": 40, "image": "/assets/items/shama-tag.jpg"},
    {"name": "City Sticker", "description": "Стикер ночного города для твоей коллекции.", "rarity": "COMMON", "value": 55, "image": "/assets/items/street-lens.jpg"},
    {"name": "Chrome Key", "description": "Холодный хром и обещание новых дверей.", "rarity": "COMMON", "value": 65, "image": "/assets/items/chrome-key.svg"},
    {"name": "Pulse Badge", "description": "Пропуск в ритм большого города.", "rarity": "COMMON", "value": 75, "image": "/assets/items/pulse-badge.svg"},
    {"name": "Night Pass", "description": "Билет на ночную сторону SHAMA.", "rarity": "COMMON", "value": 90, "image": "/assets/items/night-pass.svg"},
    {"name": "Violet Chip", "description": "Фиолетовый чип с редким свечением.", "rarity": "UNCOMMON", "value": 120, "image": "/assets/items/shama-tag.jpg"},
    {"name": "Street Lens", "description": "Линза, которая видит больше обычного.", "rarity": "UNCOMMON", "value": 145, "image": "/assets/items/street-lens.jpg"},
    {"name": "Orbit Ring", "description": "Маленькая орбита для большой истории.", "rarity": "UNCOMMON", "value": 180, "image": "/assets/items/orbit-ring.svg"},
    {"name": "Signal Deck", "description": "Колода сигналов из скрытых районов.", "rarity": "UNCOMMON", "value": 220, "image": "/assets/items/signal-deck.svg"},
    {"name": "Shama Tag", "description": "Знак тех, кто знает путь в мир.", "rarity": "UNCOMMON", "value": 260, "image": "/assets/items/shama-tag.jpg"},
    {"name": "Torpedo Ball", "description": "Мяч команды TORPEDO для решающего удара.", "rarity": "RARE", "value": 500, "image": "/assets/items/torpedo-ball.jpg"},
    {"name": "Torpedo Scarf", "description": "Шарф с цветами трибун TORPEDO.", "rarity": "RARE", "value": 650, "image": "/assets/items/torpedo-scarf.jpg"},
    {"name": "Torpedo Boots", "description": "Бутсы для тех, кто ускоряет игру.", "rarity": "RARE", "value": 800, "image": "/assets/items/torpedo-boots.jpg"},
    {"name": "Torpedo Jersey", "description": "Игровая форма легендарного сезона.", "rarity": "EPIC", "value": 1200, "image": "/assets/cases/torpedo.jpg"},
    {"name": "Torpedo Trophy", "description": "Трофей, который помнит каждый финал.", "rarity": "LEGENDARY", "value": 2400, "image": "/assets/cases/torpedo.jpg"},
    {"name": "Shama Prism", "description": "Призма с энергией центральной площади.", "rarity": "RARE", "value": 700, "image": "/assets/items/street-lens.jpg"},
    {"name": "Midnight Radio", "description": "Радио с голосами из другого измерения.", "rarity": "EPIC", "value": 1500, "image": "/assets/items/royal-visor.jpg"},
    {"name": "Ghost Jacket", "description": "Куртка, растворяющаяся в неоновом свете.", "rarity": "EPIC", "value": 1800, "image": "/assets/cases/shadow.jpg"},
    {"name": "Royal Visor", "description": "Визор для тех, кто видит карту целиком.", "rarity": "LEGENDARY", "value": 3200, "image": "/assets/items/royal-visor.jpg"},
    {"name": "Void Compass", "description": "Компас, указывающий на неизвестное.", "rarity": "MYTHIC", "value": 6000, "image": "/assets/items/shadow-mask.jpg"},
    {"name": "Solar Core", "description": "Сердце, собранное из солнечного импульса.", "rarity": "MYTHIC", "value": 7500, "image": "/assets/items/solar-core.jpg"},
    {"name": "Shadow Mask", "description": "Маска для тихих маршрутов SHAMA.", "rarity": "RARE", "value": 900, "image": "/assets/items/shadow-mask.jpg"},
    {"name": "Obsidian Blade", "description": "Черное лезвие с мягким фиолетовым бликом.", "rarity": "EPIC", "value": 2100, "image": "/assets/cases/shadow.jpg"},
    {"name": "Crown of Echoes", "description": "Корона тех, чьи истории не забывают.", "rarity": "LEGENDARY", "value": 4500, "image": "/assets/items/crown-of-echoes.jpg"},
    {"name": "World Seed", "description": "Мифическое зерно будущего мира.", "rarity": "MYTHIC", "value": 10000, "image": "/assets/items/solar-core.jpg"},
]

CASES = [
    {"name": "STARTER CASE", "description": "Первый шаг в коллекцию SHAMA WORLD.", "price": 100, "image": "/assets/cases/starter.jpg", "drops": [("Neon Token", .50), ("Violet Chip", .30), ("Torpedo Ball", .15), ("Torpedo Jersey", .04), ("Torpedo Trophy", .01)]},
    {"name": "STREET CASE", "description": "Ритм улиц, редкие сигналы и ночной стиль.", "price": 300, "image": "/assets/cases/street.jpg", "drops": [("City Sticker", .30), ("Street Lens", .35), ("Shama Prism", .25), ("Midnight Radio", .08), ("Royal Visor", .02)]},
    {"name": "TORPEDO CASE", "description": "Футбольная энергия TORPEDO внутри каждого открытия.", "price": 750, "image": "/assets/cases/torpedo.jpg", "drops": [("Torpedo Ball", .30), ("Torpedo Scarf", .25), ("Torpedo Boots", .25), ("Torpedo Jersey", .18), ("Torpedo Trophy", .02)]},
    {"name": "SHADOW CASE", "description": "Темная серия для охотников за эпическими предметами.", "price": 1500, "image": "/assets/cases/shadow.jpg", "drops": [("Shadow Mask", .30), ("Ghost Jacket", .35), ("Obsidian Blade", .25), ("Royal Visor", .08), ("Void Compass", .02)]},
    {"name": "LEGEND CASE", "description": "Самые редкие сигналы мира собраны в одном кейсе.", "price": 5000, "image": "/assets/cases/legend.jpg", "drops": [("Midnight Radio", .30), ("Royal Visor", .35), ("Crown of Echoes", .20), ("Solar Core", .10), ("World Seed", .05)]},
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
        offers = connection.execute("SELECT id, value FROM items ORDER BY ((id + ?) % 11), id LIMIT 8", (rotation_id,)).fetchall()
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
