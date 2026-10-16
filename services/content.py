"""Add catalog rows using stable names; preserve every existing item identifier."""
from __future__ import annotations
import re
from database import get_connection
from game_config import NEW_ITEMS, ENTERPRISES, BUSINESS_CASES, COLLECTION_CASES


def asset_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if slug:
        return slug
    known = {
        "Планшет «Орбита»": "orbita-tablet", "Наушники «Студия»": "studio-headphones",
        "Умные часы «Хронограф»": "chronograph-smartwatch", "Смартфон": "smartphone",
        "Стартовый": "starter-case", "Неоновый": "street-case", "Золотой": "metal-case",
        "Технологический": "timepiece-case", "Загадочный": "shadow-case", "Легендарный": "legend-case",
        "Автомобильный": "motor-case", "Королевский": "collector-case",
        "Начинающий бизнесмен": "business-case", "Предприниматель": "business-elite-case",
        "Бизнес-магнат": "business-imperial-case",
    }
    return known.get(name, "item")


def seed_game_content(path: str) -> None:
    """Idempotently seed canonical V15 catalog while preserving player-owned IDs/data."""
    from seed_data import CASES
    with get_connection(path) as c:
        c.execute("BEGIN IMMEDIATE")
        for name, category, rarity, value, variant in NEW_ITEMS:
            slug = asset_slug(name)
            # Explicit image names for non-slug legacy asset conventions.
            image = f"/assets/items/{slug}.svg"
            c.execute("INSERT OR IGNORE INTO items(name,description,rarity,value,image,category) VALUES (?,?,?,?,?,?)",
                      (name, "Коллекционный предмет SHAMA WORLD. Цена указана для мгновенного выкупа.", rarity, value, image, category))
            c.execute("UPDATE items SET category=?, value=?, rarity=? WHERE name=?", (category, value, rarity, name))
        # Fill categories for legacy collection items without deleting player-owned records.
        for row in c.execute("SELECT id,name,image FROM items WHERE category='COLLECTIBLE'").fetchall():
            name, image = row["name"].lower(), row["image"]
            category = ("CAR" if "/car-" in image else "PROPERTY" if "/house-" in image else
                        "SNEAKERS" if "jordan" in name else "WATCH" if "watch" in name else
                        "METAL" if " bar" in name else "CLOTHING" if "hoodie" in name or "jacket" in name else
                        "TROPHY" if any(x in name for x in ("medal", "trophy", "cup", "football")) else "COLLECTIBLE")
            c.execute("UPDATE items SET category=? WHERE id=?", (category, row["id"]))
        # Upsert the 14 approved businesses. Existing owned-business references remain valid.
        for code, name, price, revenue, expenses, capacity, rarity in ENTERPRISES:
            c.execute("""INSERT INTO enterprise_catalog(code,name,original_price,revenue,expenses,capacity,rarity,image)
                VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET name=excluded.name,
                original_price=excluded.original_price,revenue=excluded.revenue,expenses=excluded.expenses,
                capacity=excluded.capacity,rarity=excluded.rarity,image=excluded.image""",
                (code,name,price,revenue,expenses,capacity,rarity,f"/assets/enterprises/{code}.svg"))
        # Rename legacy case rows in-place so opening history keeps its foreign keys.
        aliases = {"STARTER CASE":"Стартовый", "STREET CASE":"Неоновый", "TORPEDO CASE":"Золотой",
                   "SHADOW CASE":"Технологический", "LEGEND CASE":"Легендарный"}
        for old, new_name in aliases.items():
            existing = c.execute("SELECT id FROM cases WHERE name=?", (old,)).fetchone()
            target = c.execute("SELECT id FROM cases WHERE name=?", (new_name,)).fetchone()
            if existing and not target:
                c.execute("UPDATE cases SET name=? WHERE id=?", (new_name, existing["id"]))
        # Canonical ordinary cases. Update prices/names/images and replace pools intentionally.
        for case in CASES:
            c.execute("""INSERT INTO cases(name,description,price,image,kind,style,active)
                VALUES (?,?,?,?, 'ITEM', ?,1) ON CONFLICT(name) DO UPDATE SET
                description=excluded.description,price=excluded.price,image=excluded.image,
                kind='ITEM',style=excluded.style,active=1""",
                (case["name"],case["description"],case["price"],case["image"],"gold"))
            case_id = c.execute("SELECT id FROM cases WHERE name=?", (case["name"],)).fetchone()[0]
            c.execute("DELETE FROM case_drops WHERE case_id=?", (case_id,))
            for item_name, chance in case["drops"]:
                item = c.execute("SELECT id FROM items WHERE name=?", (item_name,)).fetchone()
                if not item:
                    raise ValueError(f"Не найдена награда обычного кейса: {item_name}")
                c.execute("INSERT INTO case_drops(case_id,item_id,chance) VALUES (?,?,?)", (case_id,item["id"],chance))
        # Business case pools and prices are authoritative and are safe to update in place.
        for case in BUSINESS_CASES:
            c.execute("""INSERT INTO cases(name,description,price,image,kind,style,active)
                VALUES (?,?,?,?,'BUSINESS',?,1) ON CONFLICT(name) DO UPDATE SET
                description=excluded.description,price=excluded.price,image=excluded.image,
                kind='BUSINESS',style=excluded.style,active=1""",
                (case["name"],"Бизнес-кейс с предприятиями и почасовым доходом.",case["price"],
                 f"/assets/cases/{asset_slug(case['name'])}.svg",case["style"]))
            case_id = c.execute("SELECT id FROM cases WHERE name=?", (case["name"],)).fetchone()[0]
            c.execute("DELETE FROM enterprise_drops WHERE case_id=?", (case_id,))
            for code, chance in case["drops"]:
                target = c.execute("SELECT id FROM enterprise_catalog WHERE code=?", (code,)).fetchone()
                if not target:
                    raise ValueError(f"Не найден бизнес для кейса: {code}")
                c.execute("INSERT INTO enterprise_drops(case_id,enterprise_type_id,chance) VALUES (?,?,?)", (case_id,target["id"],chance))
        # Keep old collection case records for historical references but hide them from new play.
        canonical = {c["name"] for c in CASES} | {c["name"] for c in BUSINESS_CASES}
        for row in c.execute("SELECT id,name FROM cases").fetchall():
            if row["name"] not in canonical:
                c.execute("UPDATE cases SET active=0 WHERE id=?", (row["id"],))
        c.commit()
