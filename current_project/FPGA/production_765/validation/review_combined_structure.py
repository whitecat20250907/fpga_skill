"""Check actual physical font, memory and packed two-FF synchronizer bindings.

Structural evidence only: timing, Gray bus flight times, MTBF and physical
camera/DSI/PCIe operation retain their separate acceptance requirements.
"""
import argparse
import collections
import copy
import csv
import hashlib
import json
import re
from pathlib import Path

X = Path(__file__).resolve().parents[1]


def ref(p):
    return dict(path=str(p.resolve()), sha256=hashlib.sha256(p.read_bytes()).hexdigest())


def norm(s):
    return "".join(s.split())


def native_text(path):
    raw = path.read_bytes()
    try:
        return raw.decode("utf8")
    except UnicodeDecodeError:
        return raw.decode("gb18030")


def parse_cells(text):
    cells = []
    for m in re.finditer(r"^\s*(PH1_PHY_\w+)\s*#\((.*?)\)\s+(\\\S+|\w+)\s*\((.*?)\);", text, re.S | re.M):
        params = dict(re.findall(r'\.([A-Za-z0-9_]+)\("([^"\n]*)"\)', m[2]))
        ports = {k: norm(v) for k, v in re.findall(r"\.([A-Za-z0-9_]+)\((.*?)\)", m[4], re.S)}
        cells.append(dict(kind=m[1], name=m[3].lstrip("\\"), params=params, ports=ports, raw=m[2]))
    assert len(cells) > 10000, "Incomplete physical export"
    return cells


def uses(cells, signal):
    # Physical scalar signals have explicit bit selects. A matching substring
    # followed by a bracket, alphanumeric or '_' would be a different name.
    pat = re.compile(re.escape(signal) + r"(?![\w\[])" )
    return [(c, pin) for c in cells for pin, value in c["ports"].items() if pat.search(value)]


def check_pair(cells, async_names, first, second):
    first_uses = uses(cells, first)
    assert len(first_uses) == 2, (first, "First-stage Q has extra/missing physical users",
                                 [(c["name"], pin) for c, pin in first_uses])
    drivers = [(c, pin) for c, pin in first_uses if pin in ("oqa", "oqb")]
    assert len(drivers) == 1, (first, "No unique registered first-stage driver")
    a, qa = drivers[0]
    consumers = [(c, pin) for c, pin in first_uses if (c["name"], pin) != (a["name"], qa)]
    b, db = consumers[0]
    qb = next((pin for pin in ("oqa", "oqb") if b["ports"].get(pin) == second), None)
    assert qb, (first, "First stage does not exclusively drive the expected second FF")
    for cell, q in ((a, qa), (b, qb)):
        lane = q[-1].upper()
        assert cell["kind"] in ("PH1_PHY_LSLICE", "PH1_PHY_MSLICE"), cell["kind"]
        assert cell["name"] in async_names, (cell["name"], "Missing physical ASYNC_REG")
        p = cell["params"]
        assert p["LATCHMODE"] == "DFF" and p["CLKMUX"] == "SIG"
        assert p["OQ" + lane + "MUX"] == "Q" + lane
        assert p["CE" + lane + "MUX"] == "1", (cell["name"], "Gated synchronizer")
        assert p["REG" + lane + "_REGSET_ASYNC"] == "RESET"
    second_lane = qb[-1].upper()
    assert b["params"]["REG" + second_lane + "_SD"].lower() == db
    assert a["ports"]["clk"] == b["ports"]["clk"], "Synchronizer FFs have different physical clocks"
    return dict(first=first, second=second, first_cell=a["name"], first_Q=qa,
                second_cell=b["name"], second_D=db, second_Q=qb,
                clock=a["ports"]["clk"], both_physical_ASYNC_REG=True,
                first_Q_exclusively_second_D=True,
                first_D=a["params"]["REG" + qa[-1].upper() + "_SD"].lower())


def font_review(cells, words):
    prefix = "u_twin_pcie_ui/u_dashboard/"
    selected = [c for c in cells if c["kind"] == "PH1_PHY_ERAM" and c["name"].startswith(prefix + "u_glyph_rom/")]
    assert len(selected) == 4
    planes = {k: bytes((w >> k) & 1 for w in words) for k in range(16)}
    covered = []; bindings = []
    for c in selected:
        raw = c["raw"]; p = c["ports"]
        width = int(c["params"]["DATA_WIDTH_A"])
        assert width == int(c["params"]["DATA_WIDTH_B"])
        data = {int(k, 16): int(v, 16) for k, v in re.findall(r"\.INIT_([0-9A-F]{2})\(256'h([0-9A-Fa-f]+)\)", raw)}
        parity = {int(k, 16): int(v, 16) for k, v in re.findall(r"\.INITP_([0-9A-F]{2})\(256'h([0-9A-Fa-f]+)\)", raw)}
        assert set(data) == set(range(64)) and set(parity) == set(range(16))
        d = sum(v << (256 * k) for k, v in data.items())
        extra = sum(v << (256 * k) for k, v in parity.items())
        if width == 5:
            assert p["addra"] == "{\\" + prefix + "u_glyph_rom/address,2'b11}"
            high, low = map(int, re.search(re.escape("\\" + prefix + "font_row") + r"\[(\d+):(\d+)\]", p["doa"]).groups())
            bit = int(re.search(re.escape("\\" + prefix + "font_row") + r"\[(\d+)\]", p["doa_extra"])[1])
            assert high - low == 3 and bit == high + 1
            bits = list(range(low, high + 1)) + [bit]
            actual = [bytes((d >> (4 * a + b)) & 1 for a in range(4096)) for b in range(4)]
            actual.append(bytes((extra >> a) & 1 for a in range(4096)))
        elif width == 1:
            assert p["addra"] == "{2'b00,\\" + prefix + "u_glyph_rom/address}"
            bits = [int(re.search(re.escape("\\" + prefix + "font_row") + r"\[(\d+)\]", p["doa"])[1])]
            actual = [bytes((d >> a) & 1 for a in range(4096))]
        else:
            raise AssertionError((c["name"], width))
        for index, bit in enumerate(bits):
            assert actual[index] == planes[bit], (c["name"], bit)
            covered.append(bit)
        bindings.append(dict(cell=c["name"], physical_width=width, output_bits=bits))
    assert sorted(covered) == list(range(16))
    return dict(actual_ERAM=4, compared_rows=4096, compared_source_bits=65536, bindings=bindings)


def main():
    parser = argparse.ArgumentParser()
    for option in ("netlist", "area", "async-inventory", "io", "out"):
        parser.add_argument("--" + option, required=True, type=Path)
    args = parser.parse_args()
    assert not args.out.exists()
    net = args.netlist.read_text(encoding="utf8")
    cells = parse_cells(net)
    byname = {c["name"]: c for c in cells}
    assert len(byname) == len(cells)
    async_names = set(re.findall(r"^cell=(.*?) async_reg=(?:1|true)\b", args.async_inventory.read_text(), re.M))
    assert async_names and async_names <= set(byname)
    area = args.area.read_text()
    resources = {key: int(re.search(r"^#" + key + r"\s+(\d+)", area, re.M)[1])
                 for key in ("lut6", "reg", "slice", "eram", "dsp")}
    erams = [c for c in cells if c["kind"] == "PH1_PHY_ERAM"]
    assert len(erams) == resources["eram"]
    words = [int(s, 16) for s in (X / "rtl/twin_font.mem").read_text().split()]
    assert len(words) == 4096
    font = font_review(cells, words)
    pairs = []
    base = "\\u_twin_pcie_ui/u_ingress/"
    for first, second, count in (("rgray_w1", "rgray_w2", 10),
                                 ("wgray_r1", "wgray_r2", 10),
                                 ("time_w1", "time_w2", 32)):
        for bit in range(count):
            pairs.append(check_pair(cells, async_names, f"{base}{first}[{bit}]", f"{base}{second}[{bit}]"))
    for name in ("ui_up_w", "request_r", "ack_w", "busy_r"):
        pairs.append(check_pair(cells, async_names, base + name + "[0]", base + name + "[1]"))
    for name in ("start_lp", "done_ui"):
        pairs.append(check_pair(cells, async_names, "\\u_twin_dsi/" + name + "[0]", "\\u_twin_dsi/" + name + "[1]"))
    # Actual physical first-Q counterexample: one LUT input illegally observes
    # a metastability stage. The same reviewer must reject it.
    bad = copy.deepcopy(cells)
    bad[0]["ports"]["first_stage_illegal_user"] = pairs[0]["first"]
    try:
        check_pair(bad, async_names, pairs[0]["first"], pairs[0]["second"])
    except AssertionError:
        counterexample_rejected = True
    else:
        raise AssertionError("Reviewer accepted an illegal first-stage fanout")
    fifo = [c for c in erams if c["name"].startswith("u_twin_pcie_ui/u_ingress/")]
    assert len(fifo) == 2
    io = args.io.read_text()
    # Preserve original camera/PCIe pin assignment as well as new DSI pins.
    expected = X / "fpga/uisrc/04_pin/imx415_pcie.adc"
    wanted = {}
    for port, attributes in re.findall(r"^set_pin_assignment\s+\{\s*([^}]*?)\s*\}\s*\{([^}]*)\}", native_text(expected), re.M):
        wanted[port.strip()] = {k: v.strip() for k, v in re.findall(r"(\w+)\s*=\s*([^;]+);", attributes)}
    # Native export_io omits the three HRIO entries in this combined DB.
    # The actual native area -io_info table still reports all 29 exact pins.
    physical_pins = {port: dict(location=location, standard=standard)
                     for port, direction, location, standard in re.findall(
                         r"^\s*(\S+)\s+(INPUT|OUTPUT|INOUT)\s+(\S+)\s+(\S+)", area, re.M)}
    assert len(wanted) == 29 and set(wanted) <= set(physical_pins)
    for port, attributes in wanted.items():
        assert physical_pins[port] == dict(location=attributes["LOCATION"], standard=attributes["IOSTANDARD"]), port
    csv_pins = {row["Signal Name"]: row for row in csv.DictReader(io.splitlines())}
    delay_differences = [dict(port=port, source_INDEL=attributes["INDEL"],
                              exported_InDelay=csv_pins[port]["InDelay"])
                         for port, attributes in wanted.items() if "INDEL" in attributes
                         and csv_pins[port]["InDelay"] != attributes["INDEL"]]
    groups = dict(collections.Counter("/".join(c["name"].split("/")[:-1]) for c in erams))
    args.out.mkdir(parents=True)
    result = dict(status="PASS_ACTUAL_FONT_MEMORY_AND_58_PACKED_SYNC_PAIRS_STRUCTURAL_ONLY",
                  resources=resources, physical_ERAM_groups=groups, font=font,
                  physical_ASYNC_REG_cells=len(async_names), checked_sync_pairs=len(pairs),
                  sync_pairs=pairs, first_stage_fanout_counterexample_rejected=counterexample_rejected,
                  FIFO_ERAM_cells=[dict(name=c["name"], params=c["params"], ports=c["ports"]) for c in fifo],
                  checked_pin_locations_and_standards=len(wanted),
                  physical_pin_bindings=physical_pins,
                  HRIO_missing_from_export_io_only=sorted(set(wanted)-set(csv_pins)),
                  input_delay_report_differences=delay_differences,
                  input_delay_setting_equivalence_accepted=False,
                  Gray_bus_flight_time_and_skew_accepted=False,
                  full_CDC_or_MTBF_accepted=False, IO_timing_accepted=False,
                  optical_or_actual_PCIe_accepted=False, full_goal_complete=False,
                  references=[ref(p) for p in (Path(__file__), args.netlist, args.area, args.async_inventory, args.io,
                                              expected, X / "rtl/twin_font.mem", X / "rtl/twin_glyph_font.mif")])
    (args.out / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(dict(status=result["status"], resources=resources, sync_pairs=len(pairs), font_ERAM=4)), flush=True)


if __name__ == "__main__":
    main()
