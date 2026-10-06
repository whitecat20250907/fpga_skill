"""Apply only the BAR0 read-qualifier regression fix to frozen PHY09."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

R = Path(__file__).resolve().parents[1]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

old = json.loads((R / 'evidence/build09_sources.json').read_text(encoding='utf-8'))
for f in old:
    p = R / 'fpga' / f['path']
    assert p.is_file() and sha(p) == f['sha256'], f['path']

c = R / 'tools/bar_decode10/imx415_pcie_top.v'
assert sha(c) == 'ec02b945fbaec411959ae7bc4f33f61a155a7e4e8f04cbd99db23fb5676d321b'
# Match the actual production-read selfcheck and regression demonstration.
pass_log = R / 'tools/bar_decode10/evidence/new_pass_20261005_080716_37548/simulation.log'
fail_log = R / 'tools/bar_decode10/evidence/old_fail_20261005_080734_7688/simulation.log'
assert 'PASS BAR_DECODE10_PRODUCTION_READ checks=268 new_errors=0' in pass_log.read_text(errors='replace')
assert 'Fatal: EXPECTED_OLD_UPPER16_ZERO_REGRESSION_DETECTED' in fail_log.read_text(errors='replace')
new = c.read_bytes()
assert new.count(b"(m_axil_araddr[19:16] == 4'h0) &&") == 1
assert b"(m_axil_araddr[31:16] == 16'h0000) &&" not in new
manifest = R / 'evidence/build10_sources.json'
archive = R / 'evidence/build10_sources.zip'
assert not manifest.exists() and not archive.exists(), 'Never replace a source freeze'

shutil.copyfile(c, R / 'fpga/uisrc/01_rtl/imx415_pcie_top.v')
p = R / 'fpga/uisrc/01_rtl/param_imx415.v'
b = p.read_bytes()
assert b.count(b'5644_0901') == 1
p.write_bytes(b.replace(b'5644_0901', b'5644_0A01'))
files = [R / 'fpga' / f['path'] for f in old]
current = [dict(path=f['path'], bytes=p.stat().st_size, sha256=sha(p))
           for f, p in zip(old, files)]
changes = [dict(path=f['path'], old_sha256=f['sha256'], new_sha256=n['sha256'])
           for f, n in zip(old, current) if f['sha256'] != n['sha256']]
assert len(changes) == 2, changes
manifest.write_text(json.dumps(current, indent=2) + '\n', encoding='utf-8')
with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
    for f, p in zip(current, files):
        z.write(p, f['path'])

record = dict(issue=1, version='0x56440a01', source_count=len(current),
    manifest_sha256=sha(manifest), archive_sha256=sha(archive), changes=changes,
    production_read_pass_log_sha256=sha(pass_log), old_regression_log_sha256=sha(fail_log),
    status='Integrated BAR read fix; fresh full TD and actual receive acceptance pending',
    contract='BAR0 1MiB aligned; mmap+0 and V4L2 direct mapping; offset[19:0]',
    unchanged='PHY09, drivers, boot, Bayer/ISP, crop and all other demos unchanged',
    deferred='CQ aperture and issue13 write aliases/WSTRB/read stalls/legacy pread alias')
(R / 'evidence/bar10_integration.json').write_text(
    json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record))
