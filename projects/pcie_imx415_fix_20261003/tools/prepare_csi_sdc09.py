"""Stage the related-clock inventory for local-PAD-clock candidate09 only."""
from pathlib import Path
import hashlib, json
R=Path(__file__).resolve().parents[1]
p=R/'fpga/uisrc/04_pin/imx415_pcie.sdc'
old=p.read_bytes()
base='u_cam_video_source/u_mipi_csi_rx/u_csi_rx_phy/u_rx_clk_gen/'
needle=(base+'U_io_clk_div_1.clkdivout}').encode()
assert old.count(needle)==1
new=old.replace(needle,(base+'U_io_clk_div_1.clkout '+base+'U_io_clk_div_1.clkdivout}').encode())
assert new.count(b'set_clock_groups -asynchronous')==old.count(b'set_clock_groups -asynchronous')==1
assert b'set_false_path' not in new
out=R/'tools/csi_local_clock09/imx415_pcie.sdc'
out.write_bytes(new)
sha=lambda b:hashlib.sha256(b).hexdigest()
record=dict(status='staged only; not integrated',source08_sha256=sha(old),candidate_sha256=sha(new),
    change='Add DIV4.clkout HS445.5 to the same related MIPI group; DIV2.clkout now PAD222.75',
    clocks_uncut='parent HS, PAD PCLK, fabric PCLK, HS sampler and byte remain related',
    frequency_constraints_changed=False)
(out.parent/'sdc_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
