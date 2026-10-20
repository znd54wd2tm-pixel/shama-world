"""One-time safe catalogue transition, followed by repeatable asset binding."""
from datetime import datetime, timezone
from pathlib import Path
import json
import time
from database import get_connection
from catalog_v16 import CATALOGS, CASE_IMAGES, weights

ROOT=Path(__file__).resolve().parents[1]

def ensure_legacy_catalog(path):
    """Fill missing rows without V15's unconditional economic overwrites."""
    from game_config import NEW_ITEMS,ENTERPRISES,BUSINESS_CASES
    from services.content import asset_slug
    with get_connection(path) as c:
        c.execute('BEGIN IMMEDIATE')
        for name,category,rarity,value,variant in NEW_ITEMS:
            c.execute('INSERT OR IGNORE INTO items(name,description,rarity,value,image,category) VALUES (?,?,?,?,?,?)',(name,'Коллекционный предмет.',rarity,value,f'/assets/items/{asset_slug(name)}.svg',category))
        for code,name,price,revenue,expenses,capacity,rarity in ENTERPRISES:
            c.execute('INSERT OR IGNORE INTO enterprise_catalog(code,name,original_price,revenue,expenses,capacity,rarity,image) VALUES (?,?,?,?,?,?,?,?)',(code,name,price,revenue,expenses,capacity,rarity,f'/assets/enterprises/{code}.svg'))
        for case in BUSINESS_CASES:
            c.execute("INSERT OR IGNORE INTO cases(name,description,price,image,kind,style,active) VALUES (?,?,?,?,'BUSINESS',?,0)",(case['name'],'Архивный бизнес-кейс',case['price'],f'/assets/cases/{asset_slug(case["name"])}.svg',case['style']))
            cid=c.execute('SELECT id FROM cases WHERE name=?',(case['name'],)).fetchone()[0]
            if not c.execute('SELECT 1 FROM enterprise_drops WHERE case_id=?',(cid,)).fetchone():
                for code,chance in case['drops']:
                    target=c.execute('SELECT id FROM enterprise_catalog WHERE code=?',(code,)).fetchone()[0]
                    c.execute('INSERT INTO enterprise_drops VALUES (?,?,?)',(cid,target,chance))
        c.commit()

def seed_world(path):
    with get_connection(path) as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute("SELECT 1 FROM finance_meta WHERE key='catalog_v16'").fetchone():
            return
        # The first schema migration can precede initial legacy content seeding.
        # Only pre-V16 catalogue rows receive legacy buyback prices here.
        c.execute('UPDATE items SET sell_price=value WHERE asset_key IS NULL AND sell_price IS NULL')
        # The legacy catalogue is kept as the recovery source. No inventory FK changes.
        bindings={}
        for collection,rows in CATALOGS.items():
            chances=weights(rows) if collection in ('starter','neon','gold') else [None]*len(rows)
            for position,(slug,title,value,alias) in enumerate(rows):
                row=c.execute('SELECT * FROM items WHERE asset_key=?',(slug,)).fetchone()
                if row is None and alias:
                    row=c.execute('SELECT * FROM items WHERE name=?',(alias,)).fetchone()
                if row is None:
                    row=c.execute('SELECT * FROM items WHERE name=? AND asset_key IS NULL',(title,)).fetchone()
                if row is None:
                    unique=title if not c.execute('SELECT 1 FROM items WHERE name=?',(title,)).fetchone() else f'{title} · {collection}'
                    rarity={'starter':'COMMON','neon':'UNCOMMON','gold':'RARE','royal':'EPIC','collection':'LEGENDARY'}[collection]
                    cur=c.execute('''INSERT INTO items(name,display_name,description,rarity,value,catalog_value,image,category,asset_key,asset_status)
                       VALUES (?,?,?,?,?,?,?,'COLLECTIBLE',?,'missing')''',
                       (unique,title,'Коллекционный предмет. Цена мгновенного выкупа ещё не утверждена.',rarity,max(1,value),value,'/assets/item-image-unavailable.svg',slug))
                    row=c.execute('SELECT * FROM items WHERE id=?',(cur.lastrowid,)).fetchone()
                c.execute('UPDATE items SET asset_key=?,display_name=?,catalog_value=? WHERE id=?',(slug,title,value,row['id']))
                # An independently generated PNG can later be added under the stable key.
                image=f'/assets/items/{slug}.png'
                if (ROOT/'web'/image.lstrip('/')).is_file():
                    c.execute("UPDATE items SET image=?,asset_status='ready' WHERE id=?",(image,row['id']))
                bindings[slug]=row['id']
                c.execute('INSERT OR REPLACE INTO catalogue_membership VALUES (?,?,?,?)',(collection,row['id'],position,chances[position]))
        # Preserve the approved absolute royal weights. New royal items remain visible
        # as collection additions with chance=null until a redistribution is approved.
        for name,cover in CASE_IMAGES.items():
            case=c.execute('SELECT * FROM cases WHERE name=?',(name,)).fetchone()
            if case is None:continue
            c.execute("UPDATE cases SET image=?,active=1,kind='ITEM',style=? WHERE id=?",(f'/assets/cases/user-{cover}.jpg',{'starter':'carbon','neon':'neon','gold':'gold','royal':'imperial','legendary':'imperial'}[cover],case['id']))
            collection={'Стартовый':'starter','Неоновый':'neon','Золотой':'gold'}.get(name)
            if collection:
                c.execute('DELETE FROM case_drops WHERE case_id=?',(case['id'],))
                for entry,chance in zip(CATALOGS[collection],weights(CATALOGS[collection])):
                    c.execute('INSERT INTO case_drops(case_id,item_id,chance) VALUES (?,?,?)',(case['id'],bindings[entry[0]],chance))
            if name=='Золотой':c.execute('UPDATE cases SET price=5000 WHERE id=?',(case['id'],))
        allowed=tuple(CASE_IMAGES)
        c.execute(f"UPDATE cases SET active=0 WHERE name NOT IN ({','.join('?' for _ in allowed)})",allowed)
        # Existing businesses retain their rates, staff, upgrades and ownership. Settle
        # their old period before updating the approved purchase prices and rules.
        from services.businesses import settle
        for r in c.execute('SELECT id,user_id FROM owned_enterprises').fetchall():
            settle(c,r['user_id'],r['id'])
        for code,price,capacity in (('kiosk',10000,1),('coffee',50000,5),('restaurant',150000,6),('fitness',800000,7),('hotel',1200000,30),('business_center',15000000,30)):
            c.execute('UPDATE enterprise_catalog SET original_price=?,capacity=? WHERE code=?',(price,capacity,code))
        c.execute("UPDATE enterprise_catalog SET no_upgrades=1,revenue=1000 WHERE code='kiosk'")
        c.execute("UPDATE enterprise_catalog SET equipment_required=1 WHERE code='coffee'")
        # Grandfather acquired coffee equipment; never stop an already operating asset.
        from catalog_v16 import COFFEE_EQUIPMENT
        c.execute("UPDATE owned_enterprises SET equipment=? WHERE catalog_id=(SELECT id FROM enterprise_catalog WHERE code='coffee')",(json.dumps({k:True for k in COFFEE_EQUIPMENT}),))
        stamp=datetime.now(timezone.utc).isoformat()
        for code,name,price,maximum in (('BANK','Bank',1000,'.02'),('COFFEE','Coffee',500,'.05'),('HOTELS','Hotels',2000,'.05'),('INDUSTRIES','Industries',1500,'.08')):
            c.execute('INSERT OR IGNORE INTO finance_companies(code,name,price,max_change,started_at,last_tick) VALUES (?,?,?,?,?,?)',(code,name,price,maximum,stamp,int(time.time()//3600)))
        c.execute("INSERT INTO finance_meta VALUES ('catalog_v16',?)",(stamp,))
        c.commit()

def seed_royal_pool(path):
    """User approved a 15% new pool; retain old rewards and their relative weights."""
    with get_connection(path) as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute("SELECT 1 FROM finance_meta WHERE key='royal_pool_15'").fetchone():return
        royal=c.execute("SELECT id FROM cases WHERE name='Королевский'").fetchone()
        if not royal:return
        old=c.execute('SELECT item_id,chance FROM case_drops WHERE case_id=?',(royal[0],)).fetchall()
        total=sum(r['chance'] for r in old)
        if not old or abs(total-1)>1e-8:raise ValueError('Королевский пул повреждён')
        c.execute('UPDATE case_drops SET chance=chance*0.85 WHERE case_id=?',(royal[0],))
        rows=CATALOGS['royal']
        for item,chance in zip(rows,weights(rows)):
            item_id=c.execute('SELECT id FROM items WHERE asset_key=?',(item[0],)).fetchone()[0]
            c.execute('INSERT INTO case_drops(case_id,item_id,chance) VALUES (?,?,?)',(royal[0],item_id,chance*.15))
            c.execute("UPDATE catalogue_membership SET proposed_chance=? WHERE collection='royal' AND item_id=?",(chance*.15,item_id))
        c.execute("INSERT INTO finance_meta VALUES ('royal_pool_15',?)",(datetime.now(timezone.utc).isoformat(),));c.commit()
