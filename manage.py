"""Local maintenance commands; never expose this module as a web endpoint."""
from __future__ import annotations
import argparse
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from config import get_settings, require_persistent_database
from database import get_connection
from seed_data import seed_content
from game_config import ENTERPRISES, BUSINESS_CASES, COLLECTION_CASES


def backup(path: Path) -> Path:
    if not path.is_file():
        raise ValueError('Файл базы не найден; проверьте DATABASE_PATH')
    directory=path.parent/'backups'
    directory.mkdir(parents=True,exist_ok=True)
    destination=directory/f"{path.stem}.manual.{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.sqlite3"
    with closing(sqlite3.connect(path)) as source,closing(sqlite3.connect(destination)) as target:
        source.backup(target)
    return destination


def validate(path: Path) -> None:
    if not path.is_file():
        raise ValueError('Файл базы не найден; проверьте DATABASE_PATH')
    with get_connection(path) as c:
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or c.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Нарушена целостность базы')
        for row in c.execute('SELECT * FROM cases'):
            table='enterprise_drops' if row['kind']=='BUSINESS' else 'case_drops'
            total=c.execute(f'SELECT SUM(chance) FROM {table} WHERE case_id=?',(row['id'],)).fetchone()[0]
            if total is None or abs(total-1)>1e-8:
                raise ValueError(f"Вероятности {row['name']} не равны 100%")
        if c.execute('SELECT 1 FROM users WHERE balance<0').fetchone():
            raise ValueError('Обнаружен отрицательный баланс')
    print('Целостность базы, балансы и вероятности всех кейсов проверены')


def apply_config(path: Path) -> None:
    with get_connection(path) as c:
        if c.execute("SELECT 1 FROM finance_meta WHERE key='catalog_v16'").fetchone():
            raise ValueError('Команда V15 apply-config отключена для V16: она заменяет утверждённые цены и пулы. Изменяйте catalog_v16.py с отдельной версионной миграцией.')
    for case in (*COLLECTION_CASES,*BUSINESS_CASES):
        if abs(sum(p for _,p in case['drops'])-1)>1e-8:
            raise ValueError(f"Неверная сумма вероятностей: {case['name']}")
    print('Резервная копия:',backup(path))
    with get_connection(path) as c:
        c.execute('BEGIN IMMEDIATE')
        from services.businesses import settle, now_utc
        now=now_utc()
        for owned in c.execute('SELECT id,user_id FROM owned_enterprises').fetchall():
            settle(c,owned['user_id'],owned['id'],now)
        for code,name,price,revenue,expenses,capacity,rarity in ENTERPRISES:
            existing=c.execute('SELECT id FROM enterprise_catalog WHERE code=?',(code,)).fetchone()
            if existing:
                occupied=c.execute('SELECT max(n) FROM (SELECT count(*) n FROM enterprise_employees s JOIN owned_enterprises o ON o.id=s.enterprise_id WHERE o.catalog_id=? GROUP BY o.id)',(existing[0],)).fetchone()[0] or 0
                if capacity < occupied:
                    raise ValueError('Лимит мест не может быть меньше уже нанятого персонала')
            c.execute('UPDATE enterprise_catalog SET name=?,original_price=?,revenue=?,expenses=?,capacity=?,rarity=? WHERE code=?',(name,price,revenue,expenses,capacity,rarity,code))
        for case in (*COLLECTION_CASES,*BUSINESS_CASES):
            row=c.execute('SELECT id,kind FROM cases WHERE name=?',(case['name'],)).fetchone()
            if not row:
                raise ValueError('Сначала выполните команду migrate')
            c.execute('UPDATE cases SET price=?,style=? WHERE id=?',(case['price'],case['style'],row['id']))
            table,column,target,key=('enterprise_drops','enterprise_type_id','enterprise_catalog','code') if row['kind']=='BUSINESS' else ('case_drops','item_id','items','name')
            c.execute(f'DELETE FROM {table} WHERE case_id=?',(row['id'],))
            for name,chance in case['drops']:
                award=c.execute(f'SELECT id FROM {target} WHERE {key}=?',(name,)).fetchone()
                if not award:raise ValueError('Не найдена награда '+name)
                c.execute(f'INSERT INTO {table}(case_id,{column},chance) VALUES(?,?,?)',(row['id'],award[0],chance))
        c.commit()
    validate(path)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('migrate','validate','backup','apply-config'))
    args=parser.parse_args()
    settings=get_settings(require_bot=False,require_webapp=False)
    require_persistent_database(settings)
    path=settings.database_path
    if args.command=='migrate':seed_content(path);validate(path)
    elif args.command=='backup':print(backup(path))
    elif args.command=='apply-config':apply_config(path)
    else:validate(path)
