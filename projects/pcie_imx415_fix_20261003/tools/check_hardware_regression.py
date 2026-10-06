"""Offline validation of the actual hardware_regression.sh predicates.

Extracts only Python definitions/constants by AST. Never runs suite discovery,
MMIO, board setup or the shell heredoc's main body. Optional Bash -n only
parses syntax. Prints JSON;
--json may save this test's own result. A PASS is not board acceptance.
"""
import argparse,ast,copy,hashlib,json,math,re,subprocess
from pathlib import Path

BASE=Path(__file__).resolve().parent.parent
SCRIPT=BASE/'tools/hardware_regression.sh'
data=SCRIPT.read_bytes()
source=data.decode('utf-8',errors='strict')
assert b'\r' not in data, 'Shell script must use LF'
assert source.count("<<'PY_REGRESSION'")==1
assert source.rstrip().endswith('PY_REGRESSION')
python_source=source.split("<<'PY_REGRESSION'\n",1)[1].rsplit('\nPY_REGRESSION',1)[0]
tree=ast.parse(python_source,filename=str(SCRIPT))
constant_names={'ERROR_KEYS','SUPPORTED_VERSIONS','CLOCK27_VERSIONS','CAM27_EXPECTED_EDGES',
 'CAM27_TOLERANCE_EDGES','HS_EXPECTED_EDGES','HS_TOLERANCE_EDGES',
 'MAX_SNAPSHOT_AGE_S','MAX_COLLECTOR_GAP_S'}
nodes=[]
for node in tree.body:
 if isinstance(node,(ast.FunctionDef,ast.ClassDef)):nodes.append(node)
 elif isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constant_names for t in node.targets):
  nodes.append(node)
namespace={'math':math,'re':re,'json':json,'LEAK_KB':1024}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SCRIPT),'exec'),namespace)
Failure=namespace['Failure']
results=[]
def case(name,call,reject=False,contains=None):
 try:result=call()
 except Failure as error:
  if not reject:raise AssertionError(name+': unexpected rejection: '+str(error)) from error
  if contains is not None:assert contains in str(error),(name,str(error),contains)
  results.append(dict(case=name,result='pass',rejection=str(error)))
 else:
  assert not reject,name+': expected Failure but accepted'
  results.append(dict(case=name,result='pass'))
  return result

def capture():
 return [dict(frame=i,sequence=i,bytesused=1280*720*3,expected=1280*720*3,error=False,
              seconds=.2+i*.02,green_fraction=0,purple_fraction=0) for i in range(32)]
def rows(version=0x56440401):
 out=[]
 for i in range(40):
  r=dict(seconds=i/10,snapshot_seq=i+1,snapshot_age=0,busy=False,
    bit_version=hex(version),raw_packets=(i+1)*100,hs_cycles_per_100ms=4950010,
    hs_cycles=(i+1)*4950010,**{k:0 for k in namespace['ERROR_KEYS']})
  if version in namespace['CLOCK27_VERSIONS']:
   r.update(hs_cycles_per_100ms=11137500,cam27_window=(i+1)*10,
    cam27_edges_per_10ms=270000,cam27_status='0x1f',cam27_locked=True,
    cam27_frequency_ok=True,cam_xclr=True,cam_config_ready=True)
  out.append(r)
 return out

def alter(base,key,value,index=None):
 r=copy.deepcopy(base)
 for i,row in enumerate(r):
  if index is None or i==index:row[key]=value(i) if callable(value) else value
 return r

def check_csi(r,version=0x56440401):
 return namespace['validate_csi'](r,.2,.82,0,version)
legacy=rows()
modern=rows(0x56440701)
vc=namespace['validate_capture'];vd=namespace['validate_driver']
case('valid_capture',lambda:vc(capture(),32,1280,720))
case('zero_capture_rows_rejected',lambda:vc([],32,1280,720),True)
case('sequence_gap_rejected',lambda:vc(alter(capture(),'sequence',999,9),32,1280,720),True)
case('valid_active_csi',lambda:check_csi(legacy))
case('zero_raw_csi_rejected',lambda:check_csi(alter(legacy,'raw_packets',0)),True)
case('nonzero_but_stale_raw_csi_rejected',lambda:check_csi(alter(legacy,'raw_packets',500)),True)
case('crc_error_rejected',lambda:check_csi(alter(legacy,'crc_errors',1,6)),True)
mid=copy.deepcopy(legacy);mid[8]['snapshot_seq']=0
case('mid_capture_snapshot_reset_rejected',lambda:check_csi(mid),True)
initial=copy.deepcopy(legacy);initial[0].update(snapshot_seq=20,crc_errors=9)
for i,r in enumerate(initial[1:],1):r['snapshot_seq']=i
case('initial_streamon_reset_allowed_old_errors_discarded',lambda:check_csi(initial))
case('missing_driver_record_rejected',lambda:vd('','',32),True)
case('driver_complete_record',lambda:vd('', '[10] DMA thread stopped: delivered=33 rejected=0 dma_errors=0',32))
case('driver_dma_error_rejected',lambda:vd('', '[10] DMA thread stopped: delivered=33 rejected=0 dma_errors=1',32),True)
case('kernel_warning_rejected',lambda:vd('', '[10] WARNING: test',32),True)
def state():
 return dict(cma=dict(CmaTotal_kB=65536,CmaFree_kB=60000),
  aer_endpoint=dict(status_available=True,asserted_flags=[],counters={'corrected':0}))
def cma_negative():
 b=state();a=state();a['cma']['CmaFree_kB']=57000
 assert namespace['check_state'](b,a)['reasons']
case('cumulative_cma_loss_rejected',cma_negative)
def aer_negative():
 b=state();a=state();a['aer_endpoint']['counters']['corrected']=1
 assert namespace['check_state'](b,a)['reasons']
case('new_aer_error_rejected',aer_negative)
# Preserve every named original offline case, rather than silently replacing it.
old=json.loads((BASE/'reports/hardware_regression_offline_validation.json').read_text())
assert {r['case'] for r in old['isolated_validator_tests']} <= {r['case'] for r in results}
assert len(results)==15
legacy_result=check_csi(legacy)
assert legacy_result['camera_clock27']['required'] is False
case('build04_12MHz_history_needs_no_27MHz_fields',lambda:check_csi(legacy))
case('build07_valid_clock_and_fresh_snapshots',lambda:check_csi(modern,0x56440701))
for version in (0x56440501,0x56440601):
 case(f'build{(version>>8)&255:02}_clock_guard',lambda v=version:check_csi(rows(v),v))
case('unsupported_version_rejected',lambda:check_csi(modern,0),True)
case('collector_version_mismatch_rejected',lambda:check_csi(modern),True)
missing=copy.deepcopy(modern);del missing[6]['bit_version']
case('collector_version_missing_rejected',lambda:check_csi(missing,0x56440701),True)
case('legacy_zero_hs_sample_rejected',lambda:check_csi(alter(legacy,'hs_cycles_per_100ms',0,6)),True)
case('stale_snapshot_despite_later_progress_rejected',lambda:check_csi(alter(modern,'snapshot_age',.251,6),0x56440701),True)
case('snapshot_age_at_limit_accepted',lambda:check_csi(alter(modern,'snapshot_age',.25),0x56440701))
case('negative_snapshot_age_rejected',lambda:check_csi(alter(modern,'snapshot_age',-.01,6),0x56440701),True)
case('nonfinite_snapshot_age_rejected',lambda:check_csi(alter(modern,'snapshot_age',float('nan'),6),0x56440701),True)
case('nonfinite_timestamp_rejected',lambda:check_csi(alter(modern,'seconds',float('nan'),6),0x56440701),True)
case('duplicate_timestamp_rejected',lambda:check_csi(alter(modern,'seconds',.5,6),0x56440701),True)
case('stale_sequence_rejected',lambda:check_csi(alter(modern,'snapshot_seq',5),0x56440701),True)
gap=copy.deepcopy(modern);del gap[4:8]
case('collector_coverage_gap_rejected',lambda:check_csi(gap,0x56440701),True)
for k in namespace['ERROR_KEYS']:
 case(k+'_during_capture_rejected',lambda key=k:check_csi(alter(modern,key,1,6),0x56440701),True)
for edges in (11115225,11159775):
 case(f'hs_inclusive_edge_{edges}',lambda e=edges:check_csi(alter(modern,'hs_cycles_per_100ms',e),0x56440701))
for edges in (0,4950010,11115224,11159776):
 case(f'hs_invalid_edge_{edges}_rejected',lambda e=edges:check_csi(alter(modern,'hs_cycles_per_100ms',e),0x56440701),True)
for edges in (269456,270544):
 case(f'cam27_inclusive_edge_{edges}',lambda e=edges:check_csi(alter(modern,'cam27_edges_per_10ms',e),0x56440701))
for edges in (0,120000,269455,270545):
 case(f'cam27_invalid_edge_{edges}_rejected',lambda e=edges:check_csi(alter(modern,'cam27_edges_per_10ms',e),0x56440701),True)
for k in ('cam27_locked','cam27_frequency_ok','cam_xclr','cam_config_ready'):
 case(k+'_false_rejected',lambda key=k:check_csi(alter(modern,key,False,6),0x56440701),True)
for bit in range(5):
 case(f'cam27_status_bit{bit}_missing_rejected',lambda n=bit:check_csi(alter(modern,'cam27_status',hex(31&~(1<<n)),6),0x56440701),True)
missing=copy.deepcopy(modern);del missing[6]['cam27_edges_per_10ms']
case('cam27_field_missing_rejected',lambda:check_csi(missing,0x56440701),True)
case('cam27_window_zero_rejected',lambda:check_csi(alter(modern,'cam27_window',0,6),0x56440701),True)
case('cam27_cached_good_but_frozen_window_rejected',lambda:check_csi(alter(modern,'cam27_window',100),0x56440701),True)
case('cam27_slow_100ms_window_rejected',lambda:check_csi(alter(modern,'cam27_window',lambda i:i+1),0x56440701),True)
case('cam27_fast_wrong_window_rejected',lambda:check_csi(alter(modern,'cam27_window',lambda i:(i+1)*100),0x56440701),True)
case('cam27_window_wrap_valid',lambda:check_csi(alter(modern,'cam27_window',lambda i:(0xffffffdf+10*i)&0xffffffff),0x56440701))
# This is specifically an idle-tail negative control. STREAMOFF resets the
# helper, clock windows stop, and counters need not retain active frequencies.
stopped=copy.deepcopy(modern)
for r in stopped[9:]:
 r.update(snapshot_seq=0,snapshot_age=99,raw_packets=0,hs_cycles_per_100ms=0,
          cam27_window=0,cam27_edges_per_10ms=0,cam27_status='0x0',
          cam27_locked=False,cam27_frequency_ok=False,cam_xclr=False,cam_config_ready=False)
 r.update({k:99 for k in namespace['ERROR_KEYS']})
case('stopped_tail_reset_clock_and_counters_not_required',lambda:check_csi(stopped,0x56440701))
valid_status=(16<<6)|0x13
cs=namespace['validate_camera_status']
case('active_calibration_valid_eye',lambda:cs(valid_status))
case('cal_done_with_zero_eye_rejected',lambda:cs(0x13),True)
case('eye_without_cal_done_rejected',lambda:cs(valid_status&~16),True)
case('active_i2c_not_done_rejected',lambda:cs(valid_status&~1),True)
case('active_clock_not_qualified_rejected',lambda:cs(valid_status&~2),True)
case('active_i2c_bus_error_rejected',lambda:cs(valid_status|8),True)
def calibration_bookend(samples,should_validate):
 calls=[];iterator=iter(samples)
 def read(offsets):
  calls.append(offsets)
  return next(iterator)
 namespace['bar_read']=read
 result=namespace['active_calibration_sample']()
 assert (result is not None)==should_validate
 assert calls==[[0x60,0x84],[0x60]],'Unexpected MMIO read range'
case('bookended_active_calibration',lambda:calibration_bookend([{0x60:1,0x84:valid_status},{0x60:1}],True))
case('stopped_camera_no_calibration_requirement',lambda:calibration_bookend([{0x60:0,0x84:0},{0x60:0}],False))
case('streamoff_during_read_no_calibration_requirement',lambda:calibration_bookend([{0x60:1,0x84:0},{0x60:0}],False))
# Structural guards: main passes the observed version, rather than relying on
# the legacy default; calibration is wired into actual per-phase operation.
assert 'collector_lead,BIT_VERSION)' in python_source
assert 'summary[\'active_calibration_first\']=validate_camera_status(active[0x84])' in python_source
assert 'calibration=active_calibration_sample()' in python_source
assert 'BIT_VERSION=current[0x5c]' in python_source
assert '[0x44,0x48,0x60,0x64,0x84,0x90,0xa4]' in python_source
assert 'if o!=0x328' in python_source
report=dict(script_sha256=hashlib.sha256(data).hexdigest(),python_heredoc_ast='pass',lf_only=True,
 old_15_cases_reproduced=True,isolated_validator_tests=results,total=len(results),
 hardware_run='not_run',bash_syntax='requires_bash_n_on_RK',
 scope='actual extracted predicates and bookended MMIO mocks; no board/driver/kernel/clock acceptance')
arg=argparse.ArgumentParser();arg.add_argument('--json',type=Path)
arg.add_argument('--bash',type=Path,help='Optional local Bash executable for syntax-only -n, never executes suite')
a=arg.parse_args()
if a.bash:
 syntax=subprocess.run([str(a.bash),'-n',str(SCRIPT)],capture_output=True,text=True,timeout=20)
 assert syntax.returncode==0,syntax.stderr
 version=subprocess.run([str(a.bash),'--version'],capture_output=True,text=True,timeout=20)
 assert version.returncode==0,version.stderr
 report.update(bash_syntax='pass',bash_executable=str(a.bash),bash_version=version.stdout.splitlines()[0])
text=json.dumps(report,indent=2)+'\n'
if a.json:a.json.write_text(text,encoding='utf-8',newline='\n')
print(text,end='')
