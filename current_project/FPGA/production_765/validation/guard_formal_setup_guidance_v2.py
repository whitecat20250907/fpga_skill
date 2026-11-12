"""Verify setup guidance separately from unchanged hold/removal uncertainty."""
import argparse
import json
import re
from pathlib import Path
import hashlib
def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def groups(text,setup_only=False):
    answer={}
    for m in re.finditer(r'^Path Group\s*:\s*(.*?)\n(.*?)(?=^Path Group\s*:|\Z)',text,re.S|re.M):
        parts=re.split(r'(?=^Slack\s*:)',m[2],flags=re.M) if setup_only else [m[2]]
        values=set()
        for part in parts:
            if setup_only and not re.search(r'^Check Type\s*:\s*setup\s*$',part,re.M):continue
            values.update(float(v) for v in re.findall(r'sdc uncertainty:\s*([-+0-9.]+)ns',part))
        if values:answer.setdefault(m[1].strip(),set()).update(values)
    assert answer,'No actual path uncertainty records';return answer


def check(baseline,report,mode,clock):
    before=groups(baseline,mode=='stricter');after=groups(report,mode=='stricter');target=clock+' -> '+clock
    assert target in before and target in after
    if mode=='stricter':assert after[target]=={.150} and min(after[target])-max(before[target])>=.100,'Actual setup guidance is not stricter'
    else:assert after[target]==before[target] and all(k in before and v<=before[k] for k,v in after.items()),'Temporary or unexplained SDC uncertainty remains'
    return dict(target=target,before=sorted(before[target]),after=sorted(after[target]),actual_reported_groups=len(after),setup_only_for_stricter_test=mode=='stricter')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',required=True,type=Path);ap.add_argument('--report',required=True,type=Path);ap.add_argument('--mode',choices=['stricter','restored'],required=True);ap.add_argument('--clock',default='pcie_fix_user_clk');ap.add_argument('--out',required=True,type=Path);a=ap.parse_args()
    assert not a.out.exists();baseline=a.baseline.read_text();report=a.report.read_text();result=check(baseline,report,a.mode,a.clock)
    original,replacement=('0.150','0.000') if a.mode=='stricter' else ('0.000','0.150')
    bad,n=re.subn(r'(sdc uncertainty:\s*)'+re.escape(original)+r'(ns)',lambda m:m[1]+replacement+m[2],report);assert n
    try:check(baseline,bad,a.mode,a.clock)
    except AssertionError:pass
    else:raise AssertionError('Corrupted actual SDC uncertainty was accepted')
    a.out.mkdir(parents=True);result.update(status='PASS_ACTUAL_STRICTER_SETUP_GUIDANCE' if a.mode=='stricter' else 'PASS_ACTUAL_ORIGINAL_SDC_UNCERTAINTY_RESTORED',negative_mutation_rejected=True,
        v1_failure_note='v1 wrongly combined unchanged hold/removal paths with setup-only uncertainty; this version separates actual Check Type.',
        references=[ref(p) for p in (Path(__file__),a.baseline,a.report)],hardware_accessed=False)
    (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');print(result['status'],flush=True)


if __name__=='__main__':main()
