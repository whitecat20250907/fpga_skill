"""Bounded local privilege adapter for the retained owner's existing RPC."""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--binding',required=True);args=ap.parse_args()
    body=json.loads(sys.stdin.read(1024))
    if body.get('command')=='people_mode':
        assert set(body)=={'command','mode'} and body['mode'] in ('single','dual')
    else:
        assert set(body)=={'command','slot'} and body['command'] in ('page','register','unregister')
        assert type(body['slot']) is int and body['slot'] in (1,2)
    binding=json.loads(Path(args.binding).read_text());row=binding['application_client_source'];p=Path(row['path'])
    assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    sys.path.insert(0,str(p.parent));spec=importlib.util.spec_from_file_location('_web_retained_client',p)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    result=m.command(binding,dict(action='application_control',application=body),timeout=45.)
    print(json.dumps(result))

if __name__=='__main__':main()
