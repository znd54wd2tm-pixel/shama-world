"""Generate reviewable manifests from an isolated seeded DB (never a live DB)."""
import sys
import json
import hashlib
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from seed_data import seed_content
from database import get_connection
from catalog_v16 import CATALOGS

root=Path(__file__).resolve().parents[1]
def run():
    (root/'.test-data').mkdir(exist_ok=True)
    db=root/'.test-data'/'asset-audit.sqlite3';seed_content(db)
    docs=root/'docs';docs.mkdir(exist_ok=True)
    with get_connection(db) as c:
        items=[]
        for r in c.execute('SELECT m.collection,m.proposed_chance,i.* FROM catalogue_membership m JOIN items i ON i.id=m.item_id ORDER BY m.collection,m.position'):
            path=root/'web'/r['image'].lstrip('/')
            items.append({'key':r['asset_key'],'item_id_in_fresh_database':r['id'],'name':r['display_name'],'collection':r['collection'],
              'reference_value':r['catalog_value'],'buyback_price':r['sell_price'],'image':r['image'],'file_exists':path.is_file(),
              'status':r['asset_status'],'chance':r['proposed_chance'],'legacy_svg_requires_review':r['asset_status']!='missing' and path.suffix.lower()=='.svg','sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None})
        cases=[dict(r) for r in c.execute('SELECT id,name,price,image FROM cases WHERE active=1 ORDER BY price')]
    data={'note':'IDs refer to a fresh database only. Existing player IDs are preserved; asset_key is the stable binding. Missing-image neutral panels are not finished art.',
          'items':items,'cases':cases,'new_generated_item_images':[]}
    (root/'web/assets/item-catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    missing=[i for i in items if i['status']=='missing']
    lines=['# Ассеты V16','',f'Каталог: {len(items)} позиций. Не подготовлено изображений: {len(missing)}.','',
      'Изображения новых предметов не генерировались: встроенный image_gen недоступен; разрешение на платный API не получено. Нейтральная панель не считается готовым ассетом.','',
      '## Подключённые обложки','', '| Кейс | Файл | SHA-256 |','|---|---|---|']
    for case in cases:
        p=root/'web'/case['image'].lstrip('/')
        lines.append(f"| {case['name']} | `{case['image']}` | `{hashlib.sha256(p.read_bytes()).hexdigest()}` |")
    lines+=['','## Сохранённые предметные изображения утверждённого каталога','', '| Предмет | Стабильный ключ | Файл |','|---|---|---|']
    for i in items:
        if i['status']!='missing':lines.append(f"| {i['name']} | `{i['key']}` | `{i['image']}` |")
    lines+=['','## Недостающие изображения','', '| Предмет | Стабильный ключ | Ожидаемый файл |','|---|---|---|']
    for i in missing:lines.append(f"| {i['name']} | `{i['key']}` | `web/assets/items/{i['key']}.png` |")
    lines+=['','## Унаследованные SVG, требующие проверки качества','']
    for i in items:
        if i['legacy_svg_requires_review']:lines.append(f"- {i['name']}: `{i['image']}`")
    lines+=['','Все старые файлы ассетов архива сохранены. Наличие файла не является подтверждением художественного качества: часть старых SVG остаётся унаследованной графикой и требует замены.','',
       'Единое поле `items.image` используется в кейсах, результатах, инвентаре, апгрейде и рынке игроков. Для новых изображений запустите `python tools/bind_item_images.py` после добавления файлов.']
    (docs/'ASSETS_V16.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    prompts=[]
    for i in missing:
        prompts.append({'key':i['key'],'output':f"web/assets/items/{i['key']}.png",'prompt':f"Use case: product-mockup. Asset type: mobile game collectible. Subject: {i['name']}. One accurate fully visible object or logical pair, square 1:1, centered composition. Detailed realistic materials, recognizable shape, premium studio lighting. Clean dark charcoal-purple background. No lettering, watermark, logos or extra objects. Preserve the actual material and color of this object; do not make everything gold. Collection: {i['collection']}."})
    (docs/'ITEM_IMAGE_PROMPTS.json').write_text(json.dumps(prompts,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'catalog':len(items),'missing':len(missing),'preserved_mapped':len(items)-len(missing),'covers':len(cases)}))

if __name__=='__main__':run()
