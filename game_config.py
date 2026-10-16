"""Canonical SHAMA WORLD V15 economy defaults, aligned with the approved spec."""
OFFLINE_HOURS = 12
# Cumulative working-hour thresholds for levels 1..5.
LEVEL_HOURS = (0, 24, 96, 264, 600)
LEVEL_BONUSES = (0, .05, .10, .15, .20)
UPGRADE_COST_RATIOS = (.10, .20, .35)
UPGRADES = {
    "equipment": {"name": "Оборудование", "effects": (.05, .10, .15), "levels": (1, 2, 3)},
    "premises": {"name": "Помещения", "effects": (.05, .10, .15), "levels": (1, 2, 3)},
    "marketing": {"name": "Маркетинг", "effects": (.05, .10, .15), "levels": (1, 2, 3)},
    "automation": {"name": "Автоматизация", "effects": (.03, .06, .10), "levels": (1, 2, 4)},
}
EMPLOYEES = {
    "worker": {"name": "Обычный сотрудник", "hire_cost": 150, "salary": 15, "bonus": 0, "level": 1},
    "experienced": {"name": "Опытный сотрудник", "hire_cost": 400, "salary": 40, "bonus": .08, "level": 1},
    "manager": {"name": "Менеджер", "hire_cost": 1000, "salary": 100, "bonus": .15, "level": 3},
}
ENTERPRISES = (
    ("kiosk", "Уличный киоск", 7000, 190, 50, 1, "COMMON"),
    ("hardware", "Магазин хозтоваров «У дома»", 10000, 270, 70, 2, "COMMON"),
    ("coffee", "Кофейня", 15000, 410, 110, 3, "COMMON"),
    ("barbershop", "Барбершоп", 20000, 540, 140, 3, "UNCOMMON"),
    ("carwash", "Автомойка", 30000, 790, 190, 4, "UNCOMMON"),
    ("clothing", "Магазин одежды", 40000, 1050, 250, 4, "UNCOMMON"),
    ("bakery", "Пекарня", 50000, 1350, 350, 5, "RARE"),
    ("restaurant", "Ресторан", 75000, 2000, 500, 6, "RARE"),
    ("fitness", "Фитнес-клуб", 100000, 2700, 700, 7, "EPIC"),
    ("dealership", "Автосалон", 150000, 4100, 1100, 8, "EPIC"),
    ("hotel", "Отель", 250000, 6800, 1800, 10, "LEGENDARY"),
    ("business_center", "Бизнес-центр", 400000, 10800, 2800, 12, "LEGENDARY"),
    ("mall", "Торговый центр", 700000, 18700, 4700, 15, "MYTHIC"),
    ("five_star_hotel", "Пятизвёздочный отель", 1000000, 27000, 7000, 20, "MYTHIC"),
)
BUSINESS_CASES = (
    {"name": "Начинающий бизнесмен", "price": 20000, "style": "bronze", "drops": (("kiosk", .30), ("hardware", .25), ("coffee", .20), ("barbershop", .15), ("carwash", .07), ("clothing", .03))},
    {"name": "Предприниматель", "price": 100000, "style": "gold", "drops": (("bakery", .35), ("restaurant", .30), ("fitness", .20), ("dealership", .10), ("hotel", .05))},
    {"name": "Бизнес-магнат", "price": 250000, "style": "imperial", "drops": (("hotel", .60), ("business_center", .25), ("mall", .12), ("five_star_hotel", .03))},
)
NEW_ITEMS = (
    ("Black Coupe", "CAR", "RARE", 2400, "black"), ("Golden Roadster", "CAR", "LEGENDARY", 12500, "gold"),
    ("Luxury SUV", "CAR", "EPIC", 5500, "suv"), ("Carbon Supercar", "CAR", "LEGENDARY", 16000, "carbon"),
    ("Executive Sedan", "CAR", "EPIC", 4400, "sedan"), ("Grand Hypercar", "CAR", "MYTHIC", 32000, "hyper"),
    ("Modern Apartment", "PROPERTY", "RARE", 3200, "apartment"), ("Blackstone House", "PROPERTY", "EPIC", 7500, "blackstone"),
    ("Golden Villa", "PROPERTY", "LEGENDARY", 18000, "villa"), ("Grand Penthouse", "PROPERTY", "MYTHIC", 38000, "penthouse"),
    ("Black Signature Hoodie", "CLOTHING", "UNCOMMON", 400, "hoodie"), ("Gold Stitch Jacket", "CLOTHING", "RARE", 1200, "jacket"),
    ("Luxury Bomber", "CLOTHING", "EPIC", 2600, "bomber"), ("Designer Cap", "ACCESSORY", "COMMON", 160, "cap"), ("Gold Chain", "ACCESSORY", "EPIC", 3000, "chain"),
    ("Jordan 3 Black Gold", "SNEAKERS", "RARE", 2200, "j3"), ("Jordan 5 Metallic", "SNEAKERS", "EPIC", 3800, "j5"),
    ("Jordan 6 Premium", "SNEAKERS", "LEGENDARY", 7500, "j6"), ("Jordan 12 Royal", "SNEAKERS", "MYTHIC", 14000, "j12"),
    ("Black Chronograph", "WATCH", "RARE", 2800, "black"), ("Gold Skeleton", "WATCH", "EPIC", 5800, "skeleton"),
    ("Platinum Edition", "WATCH", "LEGENDARY", 12000, "platinum"), ("Imperial Watch", "WATCH", "MYTHIC", 26000, "imperial"),
    ("Copper Bar", "METAL", "COMMON", 100, "copper"), ("Platinum Bar", "METAL", "EPIC", 2600, "platinum"),
    ("White Gold Bar", "METAL", "LEGENDARY", 5200, "white"), ("Black Gold Bar", "METAL", "MYTHIC", 11000, "black"),
    ("Platinum Medal", "TROPHY", "EPIC", 2400, "medal"), ("Golden Trophy", "TROPHY", "LEGENDARY", 6000, "trophy"),
    ("Golden Boot", "TROPHY", "RARE", 1700, "boot"), ("Trophy", "TROPHY", "RARE", 1100, "classic"),
    ("Планшет «Орбита»", "ELECTRONICS", "RARE", 1800, "tablet"), ("Наушники «Студия»", "ELECTRONICS", "UNCOMMON", 650, "headphones"),
    ("Умные часы «Хронограф»", "ELECTRONICS", "EPIC", 2400, "smartwatch"),
    ("iPhone 14", "ELECTRONICS", "RARE", 700, "iphone-14"), ("iPhone 14 Pro", "ELECTRONICS", "EPIC", 1000, "iphone-14-pro"),
    ("iPhone 14 Pro Max", "ELECTRONICS", "LEGENDARY", 1300, "iphone-14-pro-max"), ("iPhone 15", "ELECTRONICS", "RARE", 900, "iphone-15"),
    ("iPhone 15 Pro", "ELECTRONICS", "EPIC", 1400, "iphone-15-pro"), ("iPhone 15 Pro Max", "ELECTRONICS", "LEGENDARY", 1900, "iphone-15-pro-max"),
    ("iPhone 16", "ELECTRONICS", "RARE", 1200, "iphone-16"), ("iPhone 16 Pro", "ELECTRONICS", "EPIC", 2000, "iphone-16-pro"),
    ("iPhone 16 Pro Max", "ELECTRONICS", "LEGENDARY", 2700, "iphone-16-pro-max"), ("iPhone 17", "ELECTRONICS", "RARE", 1600, "iphone-17"),
    ("iPhone 17 Pro", "ELECTRONICS", "EPIC", 3000, "iphone-17-pro"), ("iPhone 17 Pro Max", "ELECTRONICS", "MYTHIC", 4500, "iphone-17-pro-max"),
)
COLLECTION_CASES = (
    {"name": "Неоновый", "price": 350, "style": "carbon", "drops": (("Street Hoodie", .32), ("Silver Medal", .28), ("Jordan 1", .20), ("Gold Bar", .15), ("Jordan 4", .05))},
    {"name": "Золотой", "price": 800, "style": "gold", "drops": (("Football", .28), ("Gold Medal", .18), ("Jordan 1", .25), ("Jordan 4", .26), ("Golden Boot", .03))},
    {"name": "Технологический", "price": 600, "style": "platinum", "drops": (("Neon Token", .30), ("Chrome Key", .25), ("Signal Deck", .20), ("Наушники «Студия»", .15), ("Планшет «Орбита»", .10))},
    {"name": "Загадочный", "price": 1200, "style": "imperial", "drops": (("Shadow Mask", .30), ("Gold Bar", .25), ("Luxury Watch", .20), ("Platinum Bar", .15), ("Black Chronograph", .10))},
    {"name": "Королевский", "price": 7500, "style": "imperial", "drops": (("Supercar", .30), ("City Villa", .25), ("Golden Villa", .18), ("Grand Hypercar", .12), ("Imperial Watch", .10), ("Black Gold Bar", .05))},
    {"name": "Автомобильный", "price": 1500, "style": "carbon", "drops": (("Black Coupe", .38), ("Executive Sedan", .25), ("Luxury SUV", .20), ("Golden Roadster", .10), ("Carbon Supercar", .05), ("Grand Hypercar", .02))},
)
