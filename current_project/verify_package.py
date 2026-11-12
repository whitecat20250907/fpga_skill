from pathlib import Path
import hashlib,json,sys
p=Path(__file__).resolve().parent
m=json.loads((p/'SOURCE_MANIFEST.json').read_text(encoding='utf8'))
bad=[]
for name,row in m['files'].items():
 f=p/name
 if not f.is_file() or f.stat().st_size!=row['bytes'] or hashlib.sha256(f.read_bytes()).hexdigest()!=row['sha256']:bad.append(name)
print('PASS' if not bad else 'FAIL',len(m['files']),'files')
for name in bad:print(name)
sys.exit(bool(bad))
