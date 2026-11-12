"""Relocate the project, audit pin/files, regenerate hashed TD staging config."""
from pathlib import Path
import sys,re,hashlib,subprocess,json
P=Path(__file__).resolve().parent
def main():
 project=P/'imx415_pcie_4k.al';text=project.read_text(encoding='utf-8')
 match=re.search(r'<Project[^>]*Path="([^"]+)"',text)
 if not match:raise RuntimeError('Project path absent')
 previous=match[1];text=text.replace(previous,P.as_posix());project.write_text(text,encoding='utf-8')
 template=P/'td_build_direct.tcl';text=template.read_text(encoding='utf-8')
 text=re.sub(r'^set trace_guard_python .*$',f'set trace_guard_python {{{Path(sys.executable).as_posix()}}}',text,flags=re.M)
 text=re.sub(r'^set trace_guard_script .*$',f'set trace_guard_script {{{(P/"validation/guard_trace_eram_gate_v1.py").as_posix()}}}',text,flags=re.M)
 template.write_text(text,encoding='utf-8')
 helper=P/'candidate_control_attribute.tcl';text=helper.read_text(encoding='utf-8')
 text=re.sub(r'^set (monitor_guard_python|candidate_guard_python) .*$',lambda m:f'set {m[1]} {{{Path(sys.executable).as_posix()}}}',text,flags=re.M)
 for key,name in [('monitor_guard_script','guard_clock_monitor_cdc_v7.py'),('monitor_guard_parser','review_combined_structure.py'),('candidate_guard_script','guard_ui_up_source_pair_v2.py'),('candidate_guard_parser','review_combined_structure.py')]:
  text=re.sub(r'^set '+key+r' .*$',f'set {key} {{{(P/"validation"/name).as_posix()}}}',text,flags=re.M)
 helper.write_text(text,encoding='utf-8')
 config=P/'build_direct_config.tcl'
 cmd=[sys.executable,str(P/'validation/td_reuse_audit.py'),'audit','--project',str(project),'--direct-config',str(config),'--fix-hold-high']
 r=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8');(P/'validation/build_inventory.json').write_text(r.stdout,encoding='utf-8')
 if r.returncode:print(r.stdout,r.stderr);return r.returncode
 files=[*(P.glob('*.tcl')),*(P/'validation').glob('*.py'),P/'uisrc/04_project_twin/hmi_font.vh']
 existing=config.read_text(encoding='utf-8')
 with config.open('a',encoding='utf-8') as f:
  for path in files:
   if not path.is_file():continue
   relative=path.relative_to(P).as_posix();data=path.read_bytes()
   if path==config:continue
   if '{'+relative+'}' in existing:continue
   f.write(f'\nlappend td_direct_stage_files [list {{{relative}}} {{{len(data)}}} {{{int(path.stat().st_mtime)}}} {{{hashlib.sha256(data).hexdigest()}}}]\n')
 print('PASS: project dependency/pin inventory and source staging regenerated');return 0
if __name__=='__main__':raise SystemExit(main())

