"""Integrate issue1 only, after native golden and tiny routed STA acceptance."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

R = Path(__file__).resolve().parents[1]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

old = json.loads((R / 'evidence/build08_sources.json').read_text(encoding='utf-8'))
for f in old:
    p = R / 'fpga' / f['path']
    assert p.is_file() and sha(p) == f['sha256'], f['path']

candidate = R / 'tools/csi_local_clock09'
frozen = json.loads((candidate / 'manifest09b_frozen.json').read_text(encoding='utf-8'))
assert frozen['functional_native_golden']['result'] == 'PASS'
assert frozen['small_physical_trial']['setup_ns'] >= 0
assert frozen['small_physical_trial']['hold_ns'] >= 0
assert frozen['small_physical_trial']['no_false_path_or_frequency_relaxation']
copies = [
    ('rx_clk_gen.v', 'uisrc/03_ip/mipi_csi_2/rx_clk_gen.v',
     '3c568be86e4bed43ebab2e5318aced934993ee043b0c7b2137c4c3116034ef13'),
    ('csi_rx_phy.v', 'uisrc/03_ip/mipi_csi_2/csi_rx_phy.v',
     'df203275a110d9889fc027a2a261315f77284f22899ac38e2cd090a56fef3905'),
    ('csi_rx_hs_data_phy.v', 'uisrc/03_ip/mipi_csi_2/csi_rx_hs_data_phy.v',
     'a8161b7d0eae646302e8e4265c90ee63ee8e5ee0b2a96f9ed1f1f1517d25a4d9'),
    ('imx415_pcie.sdc', 'uisrc/04_pin/imx415_pcie.sdc',
     'd788321f228e648f4ac629602d7d77d8fd6c8e8e4dcf14eede50341c2db1dc22'),
]
for src, dst, h in copies:
    assert sha(candidate / src) == h, src
    if src != 'imx415_pcie.sdc':
        assert frozen['source_frozen'][src] == h, src
for name, h in frozen['matched_exports'].items():
    assert sha(R / frozen['small_physical_trial']['output'] / name) == h, name

manifest = R / 'evidence/build09_sources.json'
archive = R / 'evidence/build09_sources.zip'
assert not manifest.exists() and not archive.exists(), 'Never replace a source freeze'
for src, dst, h in copies:
    shutil.copyfile(candidate / src, R / 'fpga' / dst)
    assert sha(R / 'fpga' / dst) == h, dst

p = R / 'fpga/uisrc/01_rtl/param_imx415.v'
b = p.read_bytes()
assert b.count(b'5644_0801') == 1
p.write_bytes(b.replace(b'5644_0801', b'5644_0901'))
files = [R / 'fpga' / f['path'] for f in old]
new = [dict(path=f['path'], bytes=p.stat().st_size, sha256=sha(p))
       for f, p in zip(old, files)]
changes = [dict(path=f['path'], old_sha256=f['sha256'], new_sha256=n['sha256'])
           for f, n in zip(old, new) if f['sha256'] != n['sha256']]
assert len(changes) == 5, changes
manifest.write_text(json.dumps(new, indent=2) + '\n', encoding='utf-8')
with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
    for f, p in zip(new, files):
        z.write(p, f['path'])

record = dict(issue=1, version='0x56440901', source_count=len(new),
    manifest_sha256=sha(manifest), archive_sha256=sha(archive), changes=changes,
    status='Integrated; full TD, SDF injection and actual board acceptance pending',
    candidate_manifest_sha256=sha(candidate / 'manifest09b_frozen.json'),
    unchanged='Drivers, boot, Bayer/ISP behavior, crop, diagnostics08 and other demos unchanged',
    acceptance='Native digital golden and tiny routed STA are separate from full project and board')
(R / 'evidence/phy09_integration.json').write_text(
    json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record))
