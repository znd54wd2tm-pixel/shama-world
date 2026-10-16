"""Package source only and verify completeness against the supplied archive."""
from __future__ import annotations
import argparse
import hashlib
import os
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SKIP_DIRS={'.git','.venv','__pycache__','.test-data','backups','.agents','.codex'}


def files():
    for parent,dirs,names in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in SKIP_DIRS]
        for name in sorted(names):
            p=Path(parent)/name
            if name=='.env' or name.endswith(('.pyc','.log','.sqlite3','.sqlite3-wal','.sqlite3-shm','.db','.db-wal','.db-shm','.zip')):continue
            yield p


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--original',type=Path,required=True)
    args=parser.parse_args()
    old={}
    with zipfile.ZipFile(args.original) as z:
        for item in z.infolist():
            if not item.is_dir():old[item.filename.split('/',1)[1]]=hashlib.sha256(z.read(item)).hexdigest()
    current={str(p.relative_to(ROOT)).replace('\\','/'):p for p in files()}
    missing=set(old)-set(current)
    if missing:raise ValueError(f'Original files missing: {sorted(missing)}')
    manifest=[]
    for name,p in sorted(current.items()):
        if name=='CHANGESET_V15.txt':continue
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        status='ADDED' if name not in old else 'MODIFIED' if digest!=old[name] else 'UNCHANGED'
        if status!='UNCHANGED':manifest.append(f'{status:8} {name}')
    (ROOT/'CHANGESET_V15.txt').write_text('SHAMA WORLD V15 — differences from supplied ZIP\n\n'+'\n'.join(manifest)+'\n\nAll original source/asset paths remain present.\n',encoding='utf-8')
    output=ROOT.parent/'SHAMA_WORLD_V15_UPDATED.zip'
    assert output.resolve().parent==ROOT.parent.resolve()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in files():z.write(p,Path(ROOT.name)/p.relative_to(ROOT))
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise ValueError('Archive integrity error')
        entries=z.namelist()
        if any(Path(n).name=='.env' or any(part in SKIP_DIRS for part in Path(n).parts) or n.endswith(('.db','.sqlite3','.log')) for n in entries):raise ValueError('Runtime/private file included')
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(f'{digest}  {output.name}\n',encoding='ascii')
    print(f'Created {output.name}: {len(entries)} files, {output.stat().st_size:,} bytes')
    print('Original files preserved:',len(old),'; changed/added:',len(manifest))
    print('SHA256:',digest)
