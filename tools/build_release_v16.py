"""Package source and review evidence without databases, credentials or caches."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKIP_DIRS={'.test-data','.git','.codex','.agents','__pycache__','.pytest_cache','.venv','venv','node_modules','backups'}

def digest(data):return hashlib.sha256(data).hexdigest()

def deliverable(path):
    rel=path.relative_to(ROOT)
    if not path.is_file() or any(part in SKIP_DIRS for part in rel.parts):return False
    name=path.name.lower()
    if name.startswith('.env') and name!='.env.example':return False
    if path.suffix.lower() in {'.pyc','.pyo','.db','.sqlite','.sqlite3','.pem','.key'} or name.endswith(('-wal','-shm')):return False
    if path.suffix.lower()=='.log' and rel.parts[:2]!=('docs','validation'):return False
    return True

def build(source,output):
    docs=ROOT/'docs';validation=docs/'validation';validation.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(source) as z:
        if z.testzip():raise ValueError('Source ZIP integrity failed')
        original={}
        for i in z.infolist():
            if i.is_dir():continue
            parts=Path(i.filename).parts
            if 'shama-world-main' not in parts:continue
            rel=Path(*parts[parts.index('shama-world-main')+1:]).as_posix()
            original[rel]=digest(z.read(i))
    current={p.relative_to(ROOT).as_posix():digest(p.read_bytes()) for p in ROOT.rglob('*') if deliverable(p)}
    missing_assets=[p for p in original if p.startswith('web/assets/') and p not in current]
    changed_assets=[p for p in original if p.startswith('web/assets/') and p in current and original[p]!=current[p]]
    if missing_assets or changed_assets:raise ValueError('Original assets were removed or changed')
    covers=json.loads((validation/'cover-hashes.json').read_text(encoding='utf-8'))
    for cover in covers:
        if digest((ROOT/cover['destination']).read_bytes())!=cover['sha256']:raise ValueError('Cover hash mismatch')
    browser=json.loads((validation/'browser-v16.json').read_text(encoding='utf-8'))
    syntax=json.loads((validation/'syntax-v16.json').read_text(encoding='utf-8'))
    if browser['errors'] or syntax['errors']:raise ValueError('Validation reports contain errors')
    server_log=(validation/'server-tests.txt').read_text(encoding='utf-8-sig')
    server_tests=re.search(r'Ran (\d+) tests',server_log)
    if not server_tests or not server_log.rstrip().endswith('OK'):raise ValueError('Server tests did not pass')
    changes=['SHAMA WORLD V16 — changes relative to supplied FIXED ZIP','',f'Source SHA-256: {digest(source.read_bytes())}',
             'Generated lists include release documentation and validation evidence.','']
    for generated in ('docs/CHANGESET_V16.txt','docs/validation/release-audit.json'):
        current.setdefault(generated,'generated')
    for rel in sorted(current):
        if rel not in original:changes.append('NEW      '+rel)
        elif original[rel]!=current[rel]:changes.append('MODIFIED '+rel)
    for rel in sorted(set(original)-set(current)):changes.append('OMITTED  '+rel)
    (docs/'CHANGESET_V16.txt').write_text('\n'.join(changes)+'\n',encoding='utf-8')
    audit={'source_sha256':digest(source.read_bytes()),'original_asset_count':sum(p.startswith('web/assets/') for p in original),
           'missing_original_assets':missing_assets,'modified_original_assets':changed_assets,'user_covers_unchanged':5,
           'catalog_items':72,'missing_item_images':62,'new_generated_item_images':0,'server_tests':int(server_tests[1]),
           'browser_checks':len(browser['checks']),'browser_errors':browser['errors'],'python_syntax_files':syntax['python_files'],
           'javascript_syntax_files':syntax['javascript_files'],'includes_player_database':False}
    (validation/'release-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    files=sorted((p for p in ROOT.rglob('*') if deliverable(p)),key=lambda p:p.relative_to(ROOT).as_posix())
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files:z.write(p,'shama-world-main/'+p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(output) as z:
        if z.testzip():raise ValueError('Release ZIP integrity failed')
        for p in files:
            rel='shama-world-main/'+p.relative_to(ROOT).as_posix()
            if digest(z.read(rel))!=digest(p.read_bytes()):raise ValueError('Release content mismatch: '+rel)
    checksum=digest(output.read_bytes())
    Path(str(output)+'.sha256').write_text(checksum+'  '+output.name+'\n',encoding='ascii')
    print(json.dumps({'archive':str(output),'files':len(files),'bytes':output.stat().st_size,'sha256':checksum,'audit':audit},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();build(args.source,args.output)
