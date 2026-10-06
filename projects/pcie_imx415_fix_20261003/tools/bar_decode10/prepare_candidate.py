"""Prepare only the BAR0-offset decode candidate and exact production read extracts."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
SOURCE = ROOT / 'fpga/uisrc/01_rtl/imx415_pcie_top.v'
EXPECTED_SOURCE = 'fe69b14bcfd4aadd6b4debfa1d5e6d9cb6978ceb9278bc2c4142a66550339df7'


def sha(data):
    return hashlib.sha256(data).hexdigest()


old = SOURCE.read_bytes()
assert sha(old) == EXPECTED_SOURCE, 'Main09 top changed; stop rather than mix frozen versions'
needle = b"(m_axil_araddr[31:16] == 16'h0000) &&"
assert old.count(needle) == 1
new = old.replace(needle, b"(m_axil_araddr[19:16] == 4'h0) &&")
comment_anchor = b'    reg        vid_rd_sel_d1;'
assert new.count(comment_anchor) == 1
new = new.replace(comment_anchor,
    b'    // Actual RK user interface is BAR0: 1MiB, base 0x21200000.\n'
    b'    // Decode BAR0 offset [19:0]; assigned base [31:20] may be nonzero.\n'
    b'    // Keep offset [19:16] zero and low16 0x0040..0x011C to exclude IRQ 0x0128.\n'
    + comment_anchor)
(OUT / 'imx415_pcie_top.v').write_bytes(new)


def extract_read(data):
    start = data.index(b'    reg        vid_rd_sel_d1;')
    end_marker = b'    assign m_axil_rdata = vid_rd_sel_d1 ? vid_reg_rdata_d1 : app_axil_rdata;'
    end = data.index(end_marker, start) + len(end_marker)
    return data[start:end] + b'\n'


old_read = extract_read(old)
new_read = extract_read(new)
(OUT / 'production_read_old.vh').write_bytes(old_read)
(OUT / 'production_read_new.vh').write_bytes(new_read)
for source_name in ('param_tpg', 'param_imx415'):
    (OUT / (source_name + '.vh')).write_bytes(
        (ROOT / 'fpga/uisrc/01_rtl' / (source_name + '.v')).read_bytes())
record = dict(
    status='candidate only; no main edit, TD compile or board action',
    main09_top_sha256=sha(old), candidate_top_sha256=sha(new),
    old_production_read_sha256=sha(old_read), new_production_read_sha256=sha(new_read),
    bar0='0x21200000..0x212fffff, 1MiB; user driver selects BAR0',
    change='read qualifier upper31:16 zero -> BAR0 offset19:16 zero; same low16 range/case',
    source_version='0x56440901 retained; root owns any next version update',
    deferred='AXI response backpressure, write alias and WSTRB remain issue13',
    simulator_scope='exact extracted production read selector/register block, deterministic signal fixtures, sentinel app data; no PCIe/AXI engine or PHY simulation')
(OUT / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
assert SOURCE.read_bytes() == old
print(json.dumps(record, indent=2))
