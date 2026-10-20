"""Approved catalogue. Display values are deliberately separate from buyback prices.

New draw weights were authorized by the user on 2026-10-20. Royal rewards
retain their relative weights in 85% of the pool; new rewards share 15%.
"""
from decimal import Decimal

# slug, title, displayed value, existing item alias (retains ID and buyback price).
STARTER = (
 ('copper','Медь',250,'Copper Bar'), ('silver','Серебро',300,'Silver Bar'),
 ('dollars','Доллары',80,None), ('football','Футбольный мяч',650,'Football'),
 ('bronze_medal','Бронзовая медаль',120,'Bronze Medal'), ('iron_ingot','Железный слиток',180,None),
 ('steel_gear','Стальная шестерня',220,None), ('leather_football','Кожаный футбольный мяч',450,None),
 ('bronze_cup','Бронзовый кубок',350,None), ('wristwatch','Наручные часы',400,None),
 ('leather_wallet','Кожаный кошелёк',150,None), ('dollar_bundle','Пачка долларов',200,None),
 ('silver_coin','Серебряная монета',100,None), ('football_boots','Спортивные бутсы',550,None),
 ('silver_medal','Серебряная медаль',500,'Silver Medal'),
)
NEON = (
 ('neon_sneakers','Неоновые кроссовки',1200,None), ('gaming_headset','Игровая гарнитура',1500,None),
 ('gaming_keyboard','Механическая клавиатура',1800,None), ('gaming_mouse','Игровая мышь',900,None),
 ('neon_watch','Неоновые часы',2200,None), ('smartphone','Смартфон',2500,None),
 ('wireless_earbuds','Беспроводные наушники',1100,None), ('tablet','Электронный планшет',3000,None),
 ('neon_jersey','Неоновая футбольная форма',1600,None), ('purple_boots','Фиолетовые бутсы',1400,None),
 ('silver_headphones','Серебристые наушники',1700,None), ('controller','Игровой контроллер',1000,None),
 ('glowing_glasses','Светящиеся очки',800,None), ('neon_backpack','Неоновый рюкзак',1300,None),
 ('neon_dollar_bundle','Пачка долларов',2000,None),
)
GOLD = (
 ('gold_ingot','Золотой слиток',7500,'Gold Bar'), ('gold_medal','Золотая медаль',5000,'Gold Medal'),
 ('gold_watch','Золотые часы',10000,None), ('gold_chain','Золотая цепочка',4000,'Gold Chain'),
 ('gold_ring','Золотое кольцо',3500,None), ('gold_bracelet','Золотой браслет',4500,None),
 ('gold_coin','Золотая монета',2500,None), ('gold_cup','Золотой кубок',6000,'Golden Trophy'),
 ('gold_cufflinks','Золотые запонки',2000,None), ('money_clip','Золотой зажим для денег',1800,None),
 ('gold_buckle','Золотая пряжка',2200,None), ('gold_glasses','Золотые очки',3000,None),
 ('gold_pen','Золотая ручка',1500,None), ('gold_statue','Золотая статуэтка',8000,None),
 ('gold_brooch','Золотая брошь',2800,None), ('ruby','Рубин',12000,None),
 ('sapphire','Сапфир',10000,None), ('emerald','Изумруд',9000,None),
 ('briefcase','Деловой портфель',3500,None), ('business_watch','Деловые часы',4500,None),
)
ROYAL = (
 ('diamond','Бриллиант',25000,None), ('platinum_ring','Платиновое кольцо',22000,None),
 ('diamond_watch','Алмазные часы',35000,None), ('royal_scepter','Королевский скипетр',50000,None),
 ('platinum_chain','Платиновая цепочка',28000,None), ('royal_cup','Королевский кубок',40000,None),
 ('diamond_cufflinks','Бриллиантовые запонки',18000,None), ('royal_medallion','Королевский медальон',25000,None),
 ('gem_watch','Роскошные часы с камнями',45000,None), ('platinum_medal','Платиновая медаль',20000,'Platinum Medal'),
 ('aquamarine','Аквамарин',6000,None), ('amethyst','Аметист',3500,None),
 ('citrine','Цитрин',4000,None), ('garnet','Гранат',5000,None), ('black_onyx','Чёрный оникс',7000,None),
)
COLLECTION = tuple((slug,name,0,None) for slug,name in (
 ('shama_crown','Корона SHAMA'), ('tycoon_card','Карта магната'), ('owner_key','Золотой ключ владельца'),
 ('gold_skyscraper','Золотой небоскрёб'), ('tycoon_cup','Кубок магната'), ('shama_badge','Знак SHAMA'), ('shama_bank','Банк SHAMA')))
CATALOGS = {'starter':STARTER,'neon':NEON,'gold':GOLD,'royal':ROYAL,'collection':COLLECTION}
CASE_IMAGES = {'Стартовый':'starter','Неоновый':'neon','Золотой':'gold','Королевский':'royal','Легендарный':'legendary'}
# Explicit, reproducible weights. More valuable items have lower weight.
# They are not advertised as an RTP because buyback prices remain unapproved.
def weights(rows):
    raw = [Decimal(1) / Decimal(max(1,r[2])) ** 2 for r in rows]
    total = sum(raw)
    result = [float(r/total) for r in raw]
    result[-1] = 1-sum(result[:-1])
    return result

DEPOSITS = {'silver':(1000,6,'0.02'), 'gold':(10000,24,'0.05'), 'platinum':(100000,72,'0.10')}
CARDS = {'standard':(0,0,'0',25000,100000),'gold':(25000,50000,'0.10',100000,500000),
         'platinum':(150000,500000,'0.20',500000,2000000),'private':(500000,5000000,'0.30',2000000,10000000)}
LOANS = {'starter':(10000,'0.05'),'business':(100000,'0.08'),'large':(1000000,'0.12')}
TRANSFER_LIMITS = ((10,5000,2500),(20,15000,10000),(30,30000,25000),(40,50000,50000),(50,100000,100000))
# Deliberately not selected without approval; the server fails closed.
STOCK_FEE_ROUNDING = 'ceil'  # approved by the user on 2026-10-20
LARGE_TRANSFER_THRESHOLD = None
CREDIT_RATING_FORMULA = None
CRYPTO_MAX_AGE_SECONDS = 300  # technical freshness guard, not an economic rate
COFFEE_EQUIPMENT = {'machine':('Кофемашина',4000),'grinder':('Кофемолка',1000),
 'fridge':('Холодильник',1500),'display':('Витрина для выпечки',1500),
 'counter':('Стойка и касса',1000),'tables':('Столы и стулья',1000),'dishes':('Инвентарь и посуда',500)}
GOAL_REWARDS = None
SEASON_REWARDS = None
BUSINESS_PARAMETERS_STATUS = 'legacy_provisional'
COFFEE_TIER_COSTS = (50000,60000)
ADVERTISING = {'district':{'profit_multiplier':'1.5','cooldown_hours':'1.5','price':None},
               'city':{'profit_multiplier':'2','cooldown_hours':'2.5','price':None}}
