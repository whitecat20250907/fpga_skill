"""Prepare a reviewed build08 top candidate; never edits the frozen build07 tree."""
from pathlib import Path
import hashlib, json

R = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def once(s, old, new):
    assert s.count(old) == 1, (old, s.count(old))
    return s.replace(old, new)

p = R / 'fpga/uisrc/01_rtl/imx415_pcie_top.v'
assert sha(p) == '1dfe6e9303db139b23a297222d1158f206911d9da51703bb6fd673cd5e1edadf'
s = p.read_bytes().replace(b'\r\n', b'\n').decode('latin1')
s = once(s, '    reg [1:0]   reg_bayer_mode;',
    '    reg [6:0]   reg_phy_control; // E0: bit6 manual override, tap bits5:0\n'
    '    wire [223:0] phy_diag0, phy_diag1;\n'
    '    wire [31:0] phy_diag0_status, phy_diag1_status;\n'
    '    reg [1:0]   reg_bayer_mode;')
s = once(s, '        .cfg_bayer_mode     (reg_bayer_mode),',
    '        .phy_control_shadow (reg_phy_control),\n'
    '        .phy_diag0          (phy_diag0),\n'
    '        .phy_diag1          (phy_diag1),\n'
    '        .phy_diag0_status   (phy_diag0_status),\n'
    '        .phy_diag1_status   (phy_diag1_status),\n'
    '        .phy_diag0_clock_delta(),\n'
    '        .phy_diag1_clock_delta(),\n'
    '        .cfg_bayer_mode     (reg_bayer_mode),')
s = once(s, "            reg_bayer_mode  <= 2'd3;",
    "            reg_phy_control <= 7'd0; // automatic tap scan\n"
    "            reg_bayer_mode  <= 2'd3;")
s = once(s, "                    8'hD8:           reg_bayer_mode <= m_axil_wdata[1:0];",
    "                    8'hD8:           reg_bayer_mode <= m_axil_wdata[1:0];\n"
    "                    8'hE0:           reg_phy_control <= m_axil_wdata[6:0];")
s = once(s, "(m_axil_araddr[15:8] == 8'h00) &&\n"
            "                             (m_axil_araddr[7:0] >= 8'h40) &&\n"
            "                             (m_axil_araddr[7:0] <= 8'hDC)",
    "(m_axil_araddr[31:16] == 16'h0000) &&\n"
    "                             (m_axil_araddr[15:0] >= 16'h0040) &&\n"
    "                             (m_axil_araddr[15:0] <= 16'h011C)")
s = once(s, 'case (m_axil_araddr[7:0])', 'case (m_axil_araddr[15:0])')
registers = {
    0xe0: "{25'd0,reg_phy_control}", 0xe4: 'phy_diag0_status',
    0xe8: 'phy_diag0[31:0]', 0xec: 'phy_diag0[63:32]',
    0xf0: 'phy_diag0[95:64]', 0xf4: 'phy_diag0[127:96]',
    0xf8: 'phy_diag0[159:128]', 0xfc: 'phy_diag0[191:160]',
    0x100: 'phy_diag1_status', 0x104: 'phy_diag1[31:0]',
    0x108: 'phy_diag1[63:32]', 0x10c: 'phy_diag1[95:64]',
    0x110: 'phy_diag1[127:96]', 0x114: 'phy_diag1[159:128]',
    0x118: 'phy_diag1[191:160]', 0x11c: "{24'd0,phy_diag0[175:168]}"
}
new = ''.join(f"            16'h{k:04X}:             vid_reg_rdata_d1 <= {v};\n"
              for k, v in registers.items())
s = once(s, "            default:              vid_reg_rdata_d1 <= 32'd0;",
    new + "            default:              vid_reg_rdata_d1 <= 32'd0;")
out = R / 'tools/phy_diag08/imx415_pcie_top.v'
out.write_bytes(s.encode('latin1'))
record = dict(status='candidate only, not integrated or hardware tested',
    source07_top_sha256=sha(p), candidate_top_sha256=sha(out),
    read_range='0x0040..0x011C only, 16-bit decode; 0x0128 IRQ alias excluded',
    register_map={hex(k): v for k, v in registers.items()},
    manual_default=0, manual_is_diagnostic=True,
    calibration_best_window_remains_actual=True)
(R/'tools/phy_diag08/top_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
