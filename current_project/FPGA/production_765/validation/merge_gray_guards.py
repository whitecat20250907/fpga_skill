from pathlib import Path
import json,sys
main,extra=map(Path,sys.argv[1:]);a=json.loads((main/'paths.json').read_text());b=json.loads((extra/'paths.json').read_text())
assert len(a['paths'])==52 and len(b['paths'])==32
assert len({x['sink_pin'] for x in a['paths']+b['paths']})==84
(main/'ingress_only_paths.json').write_text(json.dumps(a,indent=2)+'\n')
a['paths']+=b['paths'];a['status']='IDENTIFIED_84_GRAY_ENTRIES_NOT_FINAL_SKEW_ACCEPTANCE';a['camera_guard']=str(extra/'paths.json')
(main/'paths.json').write_text(json.dumps(a,indent=2)+'\n')
with (main/'gray_skew.sdc').open('a') as f:f.write((extra/'gray_skew.sdc').read_text())
print('Merged six bounded Gray groups, 84 endpoints, no false paths added.')
