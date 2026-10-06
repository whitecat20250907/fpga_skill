"""Select suspect frames; fractions are diagnostics, never visual acceptance."""
import json,sys
from pathlib import Path
for arg in sys.argv[1:]:
    p=Path(arg)
    rows=[json.loads(s) for s in p.read_text().splitlines() if s.startswith('{')]
    if not rows:
        print(json.dumps({'path':str(p),'frames':0}));continue
    worst_p=max(rows,key=lambda r:r['purple_fraction'])
    worst_g=max(rows,key=lambda r:r['green_fraction'])
    summary=dict(path=str(p),frames=len(rows),length_or_flag_errors=sum(r['bytesused']!=r['expected'] or r['error'] for r in rows),
        sequence_gaps=sum(b['sequence']!=a['sequence']+1 for a,b in zip(rows,rows[1:])),
        fps=(len(rows)-1)/(rows[-1]['seconds']-rows[0]['seconds']) if len(rows)>1 else None,
        worst_purple=worst_p,worst_green=worst_g,
        purple_over_5pct=sum(r['purple_fraction']>.05 for r in rows),green_over_5pct=sum(r['green_fraction']>.05 for r in rows))
    p.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary))
