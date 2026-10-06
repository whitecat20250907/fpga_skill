from pathlib import Path
import fitz
import json

root = Path('E:/qianrufpga/03_MLK_AFH03_AFC03/02_hardware')
out = []
for p in root.rglob('*硬件使用手册.pdf'):
    d = fitz.open(p)
    for i, page in enumerate(d):
        t = page.get_text()
        if any(x in t.lower() for x in ['uart', '串口', 'debug', 'type-c']):
            out.append({'doc': str(p), 'page': i+1, 'text': t})
dest = Path(__file__).resolve().parents[1] / 'evidence/manual_connections.json'
dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print('Matches', len(out))
