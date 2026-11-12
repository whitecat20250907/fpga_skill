"""Prove every PAD reset driver is the same third-stage release function."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re
def review(m,cells,names):
 by={c['name']:c for c in cells};qs={}
 for c in cells:
  for q in ('oqa','oqb'):
   if q in c['ports'] and c['params'].get('OQ'+q[-1].upper()+'MUX')=='Q'+q[-1].upper():
    sig=c['ports'][q];assert sig not in qs;qs[sig]=(c,q)
 base='\\u_cam_video_source/u_mipi_csi_rx/u_csi_rx_phy/'
 first=base+'sampler_reset_meta[0]';second=base+'sampler_reset_meta[1]'
 a,qa=qs[first];z,qz=qs[second]
 def ff(c,q):
  p=c['params'];lane=q[-1].upper();d=p['REG'+lane+'_SD'].lower()
  assert p['LATCHMODE']=='DFF' and p['CLKMUX']=='SIG' and p['CE'+lane+'MUX']=='1'
  assert p['REG'+lane+'_REGSET_ASYNC']=='SET' and p['ASRMUX']=='INV' and p['SSRMUX']=='0'
  return d
 da=ff(a,qa);dz=ff(z,qz)
 assert a['name'] in names and z['name'] in names and a['ports'][da]=="1'b0" and z['ports'][dz]==first
 assert {(c['name'],pin) for c,pin in m.uses(cells,first)}=={(a['name'],qa),(z['name'],dz)}
 assert a['ports']['clk']==z['ports']['clk'] and a['ports']['asr']==z['ports']['asr']
 rows=[]
 for i in range(4):
  pad=by[f'mipi_data_hs_p[{i}]_syn_2'];assert pad['kind']=='PH1_PHY_PAD'
  sig=pad['ports']['rst'];c,q=qs[sig];d=ff(c,q)
  assert c['name'] not in names,'Distribution FF still carries ASYNC_REG optimization protection'
  assert c['ports'][d]==second,'PAD has an independent or earlier reset synchronizer'
  assert c['ports']['clk']==z['ports']['clk'] and c['ports']['asr']==z['ports']['asr']
  assert pad['ports']['isclk']==c['ports']['clk'],'PAD/driver sampling clock differs'
  rows.append(dict(lane=i,pad=pad['name'],driver_cell=c['name'],driver_Q=q,reset_signal=sig,shared_D=second,clock=c['ports']['clk'],asynchronous_reset=c['ports']['asr']))
 return dict(private_meta_pair=[a['name'],z['name']],PAD_reset_paths=rows,physical_PAD_driver_count=len({(x['driver_cell'],x['driver_Q']) for x in rows}),same_three_stage_function=True)
def main():
 ap=argparse.ArgumentParser()
 for n in ('parser','netlist','inventory','out'):ap.add_argument('--'+n,type=Path,required=True)
 a=ap.parse_args();spec=importlib.util.spec_from_file_location('physical',a.parser);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 cs=m.parse_cells(a.netlist.read_text());names=set(re.findall(r'^cell=(.*?) async_reg=(?:1|true)\b',a.inventory.read_text(),re.M))
 result=review(m,cs,names);result.update(status='PASS_ACTUAL_FOUR_PAD_SHARED_THIRD_RELEASE_FUNCTION',full_CDC_accepted=False,final_STA_accepted=False,references=[dict(path=str(f),sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for f in (Path(__file__),a.netlist,a.inventory)])
 a.out.write_text(json.dumps(result,indent=2)+'\n');print(result['status'],result['physical_PAD_driver_count'])
if __name__=='__main__':main()
