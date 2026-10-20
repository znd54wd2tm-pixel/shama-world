"""Bind verified project PNGs using stable asset keys; leave economics untouched."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from config import get_settings
from database import get_connection
from manage import backup

def main():
    root=Path(__file__).resolve().parents[1]
    settings=get_settings(require_bot=False,require_webapp=False)
    print('Backup:',backup(settings.database_path))
    count=0
    with get_connection(settings.database_path) as c:
        c.execute('BEGIN IMMEDIATE')
        for item in c.execute('SELECT id,asset_key FROM items WHERE asset_key IS NOT NULL').fetchall():
            p=root/'web/assets/items'/f'{item["asset_key"]}.png'
            if not p.is_file():continue
            if p.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError(f'Invalid PNG: {p.name}')
            c.execute("UPDATE items SET image=?,asset_status='ready' WHERE id=?",(f'/assets/items/{p.name}',item['id']));count+=1
        c.commit()
    print(f'Bound {count} PNG assets. Visual review is still required.')
if __name__=='__main__':main()
