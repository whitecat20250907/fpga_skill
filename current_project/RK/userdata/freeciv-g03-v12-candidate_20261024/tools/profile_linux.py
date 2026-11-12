"""Sample this checkout's native game processes using Linux /proc; stdlib only."""
import argparse
import json
import os
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]

def snapshot():
    result = {}
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            # A concurrent native rebuild replaces an ELF while the old
            # process keeps its inode. /proc still exposes it as '(deleted)';
            # that does not mean the process exited or stopped consuming CPU.
            target = os.readlink(p / 'exe')
            if target.endswith(' (deleted)'):target=target[:-10]
            exe = Path(target)
            if ROOT not in exe.parents or exe.name not in ('freeciv-server', 'freeciv-gtk3.22'):
                continue
            # comm may contain spaces/parentheses; the last ')' closes field 2.
            fields = (p / 'stat').read_text().rsplit(')', 1)[1].split()
            result[int(p.name)] = {
                'name': exe.name, 'start': int(fields[19]),
                'ticks': int(fields[11]) + int(fields[12]),
                'rss_bytes': int(fields[21]) * os.sysconf('SC_PAGE_SIZE'),
            }
        except (OSError, ValueError, IndexError):
            continue
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 0 < args.seconds <= 3600:
        parser.error('seconds must be in (0, 3600]')
    if not Path('/proc/self/stat').exists():
        parser.error('Linux /proc is required')
    before = snapshot()
    if not before:
        parser.error('No game processes from this checkout are running')
    start = time.monotonic()
    time.sleep(args.seconds)
    after = snapshot()
    elapsed = time.monotonic() - start
    hz = os.sysconf('SC_CLK_TCK')
    rows = []
    for pid, old in before.items():
        new = after.get(pid)
        if not new or new['start'] != old['start']:
            rows.append({'pid': pid, 'name': old['name'], 'exited': True})
            continue
        rows.append({'pid': pid, 'name': new['name'],
                     'cpu_one_core_percent': round((new['ticks']-old['ticks'])/hz/elapsed*100, 2),
                     'rss_mib': round(new['rss_bytes']/2**20, 2)})
    report = {'elapsed_seconds': round(elapsed, 3), 'logical_cpus': os.cpu_count(),
              'processes': rows, 'note': 'Native game only; RSS may double-count shared pages.'}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text+'\n', encoding='utf-8')
    print(text)

if __name__ == '__main__':
    main()
