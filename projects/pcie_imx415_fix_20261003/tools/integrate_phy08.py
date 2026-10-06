"""Apply only issue1 receive-reset/diagnostic candidates after SHA review."""
from pathlib import Path
import hashlib, json, shutil, zipfile
R = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
old = json.loads((R/'evidence/build07_sources.json').read_text())
for f in old:
    p = R/'fpga'/f['path']
    assert p.is_file() and sha(p) == f['sha256'], f['path']
copies = [
('tools/phy_diag08/imx415_pcie_top.v','fpga/uisrc/01_rtl/imx415_pcie_top.v','fe69b14bcfd4aadd6b4debfa1d5e6d9cb6978ceb9278bc2c4142a66550339df7'),
('tools/phy_diag08/cam_video_source.v','fpga/uisrc/03_ip/vid_pipeline/cam_video_source.v','47355443fcb9ad9b0f22192ccea6eee174b520927c919c2a0fa5eac1c413fa6a'),
('tools/phy_diag08/mipi_csi_rx.v','fpga/uisrc/03_ip/mipi_csi_2/mipi_csi_rx.v','afca69f2ceea234ee4737aa70e3252faa5c59027b7533e4dd6519878340e402a'),
('tools/csi_reset8/csi_rx_phy.v','fpga/uisrc/03_ip/mipi_csi_2/csi_rx_phy.v','906359628b61393e66a2c8df272acda11619287a1a1bdef3086465c120cfb05a'),
('tools/csi_reset8/csi_rx_hs_data_phy.v','fpga/uisrc/03_ip/mipi_csi_2/csi_rx_hs_data_phy.v','0beb88845db54662febcc93ed60e02553c51da7bd5b7365727616c99476f8d13')]
for src,dst,h in copies: assert sha(R/src) == h, src
manifest = R/'evidence/build08_sources.json'
archive = R/'evidence/build08_sources.zip'
assert not manifest.exists() and not archive.exists(), 'Never replace a source freeze'
for src,dst,h in copies: shutil.copyfile(R/src,R/dst)
p=R/'fpga/uisrc/01_rtl/param_imx415.v'
b=p.read_bytes(); assert b.count(b'5644_0701') == 1
p.write_bytes(b.replace(b'5644_0701',b'5644_0801'))
files=[R/'fpga'/f['path'] for f in old]
new=[dict(path=str(p.relative_to(R/'fpga')).replace('\\','/'),bytes=p.stat().st_size,sha256=sha(p)) for p in files]
manifest.write_text(json.dumps(new,indent=2)+'\n',encoding='utf-8')
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for p in files: z.write(p,str(p.relative_to(R/'fpga')).replace('\\','/'))
changes=[dict(path=f['path'],old_sha256=f['sha256'],new_sha256=n['sha256'])
         for f,n in zip(old,new) if f['sha256']!=n['sha256']]
assert len(changes)==6, changes
record=dict(issue=1,version='0x56440801',status='Integrated; TD and physical board acceptance pending',
    source_count=len(new),manifest_sha256=sha(manifest),archive_sha256=sha(archive),changes=changes,
    unchanged='Drivers, boot, Bayer/ISP behavior, crop and other demos unchanged from07')
(R/'evidence/phy08_integration.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
