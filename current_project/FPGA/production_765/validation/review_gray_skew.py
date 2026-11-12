"""Accept complete native reports for the exact registered Gray bus inventory."""
from pathlib import Path
import argparse,hashlib,json,re

def review(text,paths,commands):
 assert 'Confidence          : Routed' in text and 'Both (Slow and Fast)' in text
 buses=list(dict.fromkeys(p['bus'] for p in paths))
 expected_sizes={'rgray':10,'wgray':10,'time_gray':32}
 if len(buses)==6:expected_sizes.update(camera_rdgray=13,camera_wrgray=13,camera_presence_gray=6)
 assert buses==list(expected_sizes),'Unexpected bus inventory or ordering'
 assert len(commands)==len(buses)
 assert len({p['sink_pin'] for p in paths})==len(paths),'Duplicate destination'
 for bus,count in expected_sizes.items():assert sum(p['bus']==bus for p in paths)==count,(bus,'Wrong endpoint count')
 sections=re.split(r'(?m)^(\d+),\s+(set_path_skew[^\n]*)\n',text)
 assert len(sections)==1+3*len(buses),'Missing or extra native constraint sections'
 rows=[];groups=[]
 for j,bus in enumerate(buses):
  index,command,body=sections[1+j*3:4+j*3]
  assert int(index)==j+1 and ' '.join(command.split())==' '.join(commands[j].split()),'Native constraint identity mismatch'
  selected=[x for x in paths if x['bus']==bus]
  expected={x['sink_pin']:x['source_timing_start'] for x in selected};seen=set()
  blocks=re.split(r'(?m)^Slack\s*:',body)[1:]
  assert len(blocks)==len(expected),(bus,'Missing or duplicated endpoint reports')
  for b in blocks:
   def field(name):
    match=re.search(r'(?m)^'+re.escape(name)+r'\s*:\s*(\S+)',b);assert match,(bus,'Missing '+name);return match[1]
   end=field('Endpoint Destination');begin=field('Endpoint Source')
   ref_end=field('Reference Destination');ref_begin=field('Reference Source')
   assert end in expected and end not in seen and begin==expected[end],(bus,'Wrong endpoint/source')
   assert ref_end in expected and ref_begin==expected[ref_end],(bus,'Wrong reference path')
   seen.add(end)
   actual=float(field('Actual Path Skew').removesuffix('ns'))
   required=float(field('Requirement').removesuffix('ns'))
   slack=float(re.match(r'\s*([-\d.]+)ns',b)[1])
   assert required==4.0 and 0<=actual<required and slack>0,(bus,'Skew violation')
   assert abs(slack-(required-actual))<=0.002,(bus,'Inconsistent native slack')
   rows.append(dict(bus=bus,destination=end,actual_ns=actual,slack_ns=slack,process=field('Process')))
  assert seen==set(expected)
  groups.append(dict(bus=bus,endpoints=len(seen),worst_skew_ns=max(x['actual_ns'] for x in rows if x['bus']==bus)))
 return dict(groups=groups,rows=rows)

def main():
 p=argparse.ArgumentParser()
 for n in ('report','paths','constraints','out'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();text=a.report.read_text();paths=json.loads(a.paths.read_text())['paths']
 commands=[s.strip() for s in a.constraints.read_text().splitlines() if s.strip() and not s.lstrip().startswith('#')]
 assert len(commands) in (3,6) and all(s.startswith('set_path_skew ') for s in commands)
 result=review(text,paths,commands)
 # Reject an apparently valid report with a substituted endpoint or violated bound.
 for bad in (text.replace(result['rows'][0]['destination'],'wrong.endpoint'),re.sub(r'(?m)^(Actual Path Skew\s*:\s*)[-\d.]+ns',r'\g<1>4.001ns',text,count=1)):
  try:review(bad,paths,commands)
  except AssertionError:pass
  else:raise AssertionError('Accepted corrupted native skew report')
 result.update(status=f'PASS_{len(commands)}_NATIVE_GRAY_SKEW_CONSTRAINTS_{len(paths)}_ENDPOINTS',full_CDC_or_MTBF_accepted=False,
               negative_controls_rejected=True,references=[dict(path=str(x),sha256=hashlib.sha256(x.read_bytes()).hexdigest()) for x in (Path(__file__),a.report,a.paths,a.constraints)])
 a.out.write_text(json.dumps(result,indent=2),'utf-8');print(json.dumps(result['groups']))
if __name__=='__main__':main()
