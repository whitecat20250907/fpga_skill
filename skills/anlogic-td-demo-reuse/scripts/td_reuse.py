"""Clone and audit the six locally verified TD examples. Python stdlib only.

This is a dependency inventory, not a Verilog elaborator or timing sign-off.
Never overwrites a target, regenerates an IP, programs a board, or copies a license.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

DEMOS = {
    "01": "01_uart_loop", "02": "02_i2c_eeprom", "03": "03_iic_rtc",
    "04": "04_ddr3_axi_fdma_test", "05": "05_tpg_dsi_7cun",
    "06": "06_csi_2_dsi_imx415_7cun",
}
SKILL = Path(__file__).resolve().parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    for enc in ("utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            pass
    return path.read_text(encoding="utf-8", errors="replace")


def xml(path):
    # Some TD .al files contain literal '&' in UsedInP&R attributes.
    # Repair in memory for parsing ONLY; never serialize and rewrite these files.
    data = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)", "&amp;", read(path))
    # TD also emits non-XML names like <BitgenProperty::GeneralOption>.
    data = re.sub(r"(<\/?)([A-Za-z_][\w:.-]*)", lambda m: m[1] + m[2].replace("::", "__"), data)
    return ET.fromstring(data)


def portable_files(root):
    nested = set(DEMOS.values()) | {"07_xgudp"}
    for base, dirs, files in os.walk(root):
        base = Path(base)
        dirs[:] = sorted(d for d in dirs if not (
            d.endswith("_Runs") or d in {"log", "work", ".git", "__pycache__", "reports"}
            or (base == root and d in nested)
        ))
        for name in sorted(files):
            p = base / name
            if p.is_symlink():
                raise ValueError(f"Symlink requires manual dependency review: {p}")
            if p.suffix.lower() in {".bit", ".dmp", ".log", ".logw", ".wlf", ".vcd", ".lic", ".pyc"}:
                continue
            if name in {".lock.f", ".recent_user_depot.ini", "transcript", "clone_manifest.json"}:
                continue
            # Preserve .bin/.db/.mif/.mem/.txt: they may be IP netlists or ROM data.
            yield p


def project_info(project):
    doc = xml(project)
    refs = [n.attrib["Path"] for n in doc.findall("./Source_Files/*/File")]
    return {
        "name": doc.findtext("Name"), "device": doc.findtext("HardWare/Device"),
        "speed": doc.findtext("HardWare/Speed"), "top": doc.findtext("TOP_MODULE/MODULE"),
        "td_version": doc.findtext("TD_Version"), "project_root": doc.attrib.get("Path"),
        "source_files": refs,
    }


def direct_config(project, area_option="-packarea", mtbf_mandatory=False, fix_hold_high=False):
    """Current .al metadata, not stale *_Runs settings or checkpoints."""
    project = project.resolve()
    root, doc = project.parent, xml(project)
    runs = doc.findall("./Runs/Run")
    physical = [r for r in runs if r.get("Type") == "PhysicalDesign"]
    active = [r for r in physical if r.get("Active", "").strip().lower() == "true"]
    if len(active) != 1:
        raise ValueError("Direct build requires one active physical run in the current .al")
    phy = active[0]
    synthesis = [r for r in runs if r.get("Name") == phy.get("SynRun") and r.get("Type") == "Synthesis"]
    if len(synthesis) != 1:
        raise ValueError("Active physical run must reference a current synthesis run")
    syn = synthesis[0]
    if syn.get("ConstraintSet") != phy.get("ConstraintSet"):
        raise ValueError("Different synthesis/physical ConstraintSets require a reviewed custom direct flow")
    info = project_info(project)
    if info["device"] != "PH1A90SEG324" or info["speed"] != "-2":
        raise ValueError("This template is validated for PH1A90SEG324 speed -2 only")
    for field in ("name", "top"):
        if not info[field] or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", info[field]):
            raise ValueError(f"Unsupported or missing project {field}")
    constraints = {"adc": [], "sdc": [], "ip_adc": [], "ip_sdc": []}
    excluded_ip_constraints = []
    for group in doc.findall("./Source_Files/*"):
        files = list(group.findall("File"))
        files.sort(key=lambda f: int(next((a.get("Val", "0") for a in f.findall("./FileInfo/Attr")
                                         if a.get("Name") == "CompileOrder"), "0")))
        for entry in files:
            attrs = {a.get("Name"): a.get("Val", "").strip() for a in entry.findall("./FileInfo/Attr")}
            if attrs.get("UsedInSyn", "true").lower() != "true":
                continue
            path = (root / entry.get("Path")).resolve()
            suffix = path.suffix.lower()
            if suffix in {".adc", ".sdc"}:
                if attrs.get("BelongTo") == syn.get("ConstraintSet"):
                    constraints[suffix[1:]].append(path.as_posix())
            elif suffix in {".ipc", ".xml"}:
                ip = xml(path)
                generated = [f for f in ip.findall("./GeneratedFiles/*")
                             if f.tag in {"ADC_FILE", "SDC_FILE"} and
                             f.get("Enable", "true").strip().lower() == "true"]
                ip_device = ip.findtext("./GeneralConfig/Device")
                if generated and ip_device and ip_device != info["device"]:
                    # Multi-device vendor sources can retain another device's IP
                    # in disabled generate branches. Its physical ADC is not for
                    # this package; keep its source registration, omit constraints.
                    excluded_ip_constraints.append({"ip": path.as_posix(), "device": ip_device,
                                                    "reason": "Generated for a different device; review disabled generate branches"})
                    continue
                inst = ip.findtext("./GeneralConfig/inst")
                if generated and not inst:
                    raise ValueError(f"Missing IP constraint model name: {path}")
                for f in generated:
                    constraint = (path.parent / (f.text or "").strip()).resolve()
                    if not constraint.is_file() or not inside(constraint, root):
                        raise ValueError(f"Missing/external generated IP constraint: {constraint}")
                    constraints["ip_" + f.tag[:3].lower()].append([inst, constraint.as_posix()])
    # Stage entire registered source/IP directory trees, including ROM files
    # referenced internally by encrypted/generated IP. Do not copy old Runs.
    source_roots = set()
    root_files = {project.name}
    for ref in info["source_files"]:
        dependency = (root / ref).resolve()
        if not dependency.is_file() or not inside(dependency, root):
            raise ValueError(f"Missing/external staging dependency: {ref}")
        relative = dependency.relative_to(root)
        if len(relative.parts) == 1:
            root_files.add(relative.as_posix())
        else:
            source_roots.add(relative.parts[0])
    support_suffixes = {".mem", ".mif", ".hex", ".bin", ".txt", ".db", ".dat", ".vh", ".svh"}
    stage_files = []
    for p in portable_files(root):
        relative = p.relative_to(root)
        if (relative.parts[0] in source_roots or relative.as_posix() in root_files or
                len(relative.parts) == 1 and p.suffix.lower() in support_suffixes):
            stat = p.stat()
            stage_files.append([relative.as_posix(), stat.st_size, int(stat.st_mtime), sha(p)])
    return {"schema": 2, "project": project.as_posix(), "project_sha256": sha(project),
            "project_size": project.stat().st_size, "project_mtime": int(project.stat().st_mtime),
            "name": info["name"], "top": info["top"], "device_db": "ph1_90.db",
            "package": info["device"], "speed": 2,
            "syn_run": syn.get("Name"), "phy_run": phy.get("Name"),
            "area_option": area_option, "mtbf_mandatory": int(mtbf_mandatory), **constraints,
            "fix_hold_high": int(fix_hold_high),
            "stage_files": stage_files,
            "excluded_ip_constraints": excluded_ip_constraints,
            "validation": "Configuration parsed only; direct template TD execution pending"}


def inside(path, root):
    return path.resolve().is_relative_to(root.resolve())


def audit(project):
    project = project.resolve()
    root = project.parent
    info = project_info(project)
    errors, warnings, pins, ipfiles = [], [], [], []
    active = []
    for ref in info["source_files"]:
        p = root / ref
        if not p.is_file():
            errors.append(f"Missing project reference: {ref}")
        elif not inside(p, root):
            errors.append(f"External project dependency: {ref}")
        else:
            active.append(p)
            if p.suffix.lower() in {".ipc", ".xml"}:
                ipfiles.append(ref)
                try:
                    doc = xml(p)
                    for f in doc.iter():
                        if f.tag.split("}")[-1] != "file":
                            continue
                        names = [n.text for n in f if n.tag.split("}")[-1] == "name" and n.text]
                        for name in names:
                            q = p.parent / name
                            if not q.is_file():
                                errors.append(f"Missing IP fileSet reference: {ref} -> {name}")
                            elif not inside(q, root):
                                errors.append(f"External IP dependency: {ref} -> {name}")
                except ET.ParseError as e:
                    warnings.append(f"IP config could not be parsed: {ref}: {e}")

    # Enumerate all retained ADCs with source provenance. Some are unused alternatives.
    for p in portable_files(root):
        rel = p.relative_to(root).as_posix()
        if p.suffix.lower() == ".adc":
            adc_text = re.sub(r"(?m)^\s*#.*(?:\r?\n|$)", "", read(p))
            for sig, attrs in re.findall(r"set_(?:ip)?pin_assignment\s*\{([^}]+)\}\s*\{([^}]+)\}", adc_text):
                loc = re.search(r"LOCATION\s*=\s*([^;\s]+)", attrs)
                std = re.search(r"IOSTANDARD\s*=\s*([^;\s]+)", attrs)
                pins.append({"signal": sig.strip(), "location": loc[1] if loc else None,
                             "iostandard": std[1] if std else None, "file": rel,
                             "direct_project_constraint": p in active})
        if p.suffix.lower() in {".do", ".f", ".ini"} and re.search(r"[A-Za-z]:[/\\]", read(p)):
            warnings.append(f"Check simulator/author machine paths before running: {rel}")
    direct_sdc = [p for p in active if p.suffix == ".sdc"]
    if not direct_sdc:
        warnings.append("No project-level SDC; inspect whether IP supplies all required clocks.")
    for p in direct_sdc:
        if re.search(r"set_clock_groups\s+-exclusive", read(p)):
            warnings.append(f"Review broad exclusive clock groups/CDC before integration: {p.relative_to(root)}")
    # Only direct project ADCs can be combined automatically. IP alternatives need TD resolution.
    used = {}
    for pin in (p for p in pins if p["direct_project_constraint"] and p["location"]):
        prev = used.get(pin["location"])
        if prev and prev != pin["signal"]:
            errors.append(f"Direct ADC pin conflict: {pin['location']} -> {prev}, {pin['signal']}")
        used[pin["location"]] = pin["signal"]
    try:
        build_config = direct_config(project)
        for skipped in build_config["excluded_ip_constraints"]:
            warnings.append(f"Direct flow omits {skipped['device']} IP constraints: {skipped['ip']}; review generate branches")
    except (ValueError, OSError, ET.ParseError) as e:
        build_config = None
        warnings.append(f"Direct build configuration unavailable: {e}")
    return {**info, "project": project.as_posix(), "errors": errors, "warnings": sorted(set(warnings)),
            "direct_build": build_config,
            "ip_files": ipfiles, "pin_inventory": pins,
            "scope": "Checks explicit project/IP fileSet references and direct ADC collisions only. "
                     "TD compile must validate Verilog includes, encrypted dependencies, IP-generated constraints and timing."}


def catalog(examples):
    result = {"schema": 1, "confirmed_by_user": "2026-09-23", "examples_root": examples.as_posix(), "demos": {}}
    for key, name in DEMOS.items():
        root = examples / name
        a = audit(root / "fpga_prj.al")
        if a["errors"]:
            raise ValueError(f"{name}: {a['errors']}")
        inputs = {p.relative_to(root).as_posix(): sha(p) for p in portable_files(root)}
        run = root / "fpga_prj_Runs/phy_1"
        log = run / "run.log"
        evidence = {p.name: {"sha256": sha(p), "bytes": p.stat().st_size} for p in run.glob("*.bit")}
        timing = re.findall(r"Timing info:[^\r\n]*", read(log))[-1:] if log.is_file() else []
        result["demos"][key] = {"directory": name, "audit": a, "inputs_sha256": inputs,
                                 "bit_evidence": evidence, "latest_timing_line": timing,
                                 "evidence_note": "Current files/logs inventoried; user confirmed board operation. "
                                                  "Historical bit-to-source identity is not independently proven."}
    return result


def verify(root, baseline):
    current = {p.relative_to(root).as_posix(): sha(p) for p in portable_files(root)}
    return {"missing": sorted(set(baseline) - set(current)),
            "added": sorted(set(current) - set(baseline)),
            "changed": sorted(k for k in baseline.keys() & current.keys() if baseline[k] != current[k])}


def tcl_path(path):
    s = path.resolve().as_posix()
    if any(c in s for c in "{}\r\n"):
        raise ValueError("Tcl paths containing braces or newlines require manual handling")
    return "{" + s + "}"


def tcl_value(value):
    # Backslashes inside Tcl braces are not uniformly literal (notably \\newline).
    if any(c in str(value) for c in "{}\\\r\n"):
        raise ValueError("Tcl config values with braces, backslashes or newlines need manual handling")
    return "{" + str(value) + "}"


def write_direct_config(project, destination, area_option="-packarea", mtbf_mandatory=False, fix_hold_high=False):
    data = direct_config(project, area_option, mtbf_mandatory, fix_hold_high)
    lines = ["# Generated from CURRENT .al; regenerate after changing TOP, runs, IP or constraints.",
             "# Other HDL attributes and run parameters remain in .al (load_run_param)."]
    for key in ("schema", "project", "project_sha256", "project_size", "project_mtime", "name", "top",
                "device_db", "package", "speed", "syn_run", "phy_run", "area_option", "mtbf_mandatory", "fix_hold_high"):
        lines.append(f"set td_direct_{key} {tcl_value(data[key])}")
    for key in ("adc", "sdc"):
        lines.append(f"set td_direct_{key} [list " + " ".join(tcl_value(p) for p in data[key]) + "]")
    for key in ("ip_adc", "ip_sdc"):
        pairs = ["[list " + " ".join(tcl_value(v) for v in pair) + "]" for pair in data[key]]
        lines.append(f"set td_direct_{key} [list " + " ".join(pairs) + "]")
    entries = ["[list " + " ".join(tcl_value(v) for v in item) + "]" for item in data["stage_files"]]
    lines.append("set td_direct_stage_files [list " + " ".join(entries) + "]")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return data


def clone(source, target, baseline):
    source, target = source.resolve(), target.resolve()
    if target.exists() or inside(target, source) or inside(source, target):
        raise ValueError("Target must be new and separate from the source")
    drift = verify(source, baseline)
    if any(drift.values()):
        raise ValueError("Baseline has changed; inspect and intentionally recatalog if appropriate: " + json.dumps(drift))
    a = audit(source / "fpga_prj.al")
    if a["errors"]:
        raise ValueError(str(a["errors"]))
    project_path = tcl_path(target / "fpga_prj.al")
    root_path = tcl_path(target)
    files = list(portable_files(source))
    target.mkdir(parents=True)
    for p in files:
        q = target / p.relative_to(source)
        q.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, q)
    project = target / "fpga_prj.al"
    text = read(project)
    escaped = target.as_posix().replace("&", "&amp;").replace('"', "&quot;")
    text, count = re.subn(r'(<Project\b[^>]*\bPath=")[^"]*', lambda m: m[1] + escaped, text, count=1)
    if count != 1:
        raise ValueError("Unexpected .al project format; target retained for inspection")
    project.write_text(text, encoding="utf-8")
    (target / "build.tcl").write_text(
        "# Run from a separate TD command process; close this target in TD GUI first.\n"
        "if {[catch {\n"
        f"  cd {root_path}\n"
        "  import_device ph1_90.db -package PH1A90SEG324 -speed 2\n"
        f"  open_project {project_path}\n"
        "  set build_started [clock seconds]\n"
        "  reset_runs syn_1\n"
        "  launch_runs syn_1\n  wait_run syn_1 -quiet\n"
        "  launch_runs phy_1\n  wait_run phy_1 -quiet\n"
        "  set build_bit {fpga_prj_Runs/phy_1/fpga_prj.bit}\n"
        "  if {![file exists $build_bit] || [file mtime $build_bit] < $build_started} {\n"
        "    error {TD did not generate a fresh bitstream}\n  }\n"
        "} err]} { puts stderr $err; exit 1 }\nexit 0\n", encoding="utf-8")
    # Separate fallback: keep the original managed run flow exactly as above.
    shutil.copy2(SKILL / "scripts/td_build_direct.tcl", target / "td_build_direct.tcl")
    write_direct_config(project, target / "build_direct_config.tcl")
    (target / "build_direct.tcl").write_text(
        "# TD Windows CLI takes this ONE script path; the template consumes argv.\n"
        "set td_direct_caller_dir [file dirname [file normalize [info script]]]\n"
        "set argv [list [file join $td_direct_caller_dir fpga_prj.al] "
        "[file join $td_direct_caller_dir build_direct_config.tcl]]\n"
        "source [file join $td_direct_caller_dir td_build_direct.tcl]\n", encoding="utf-8")
    manifest = {"source": source.as_posix(), "target": target.as_posix(),
                "baseline_drift": drift, "copied_source_hashes": baseline,
                "changes": ["Relocated .al Project Path", "Added build.tcl", "Added independent direct build caller/config/template"],
                "status": "Cloned only; build and board verification pending"}
    (target / "clone_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    report = audit(project)
    (target / "audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if report["errors"]:
        raise ValueError(str(report["errors"]))
    return {"project": project.as_posix(), "copied_files": len(files), "warnings": report["warnings"],
            "managed_build": (target / "build.tcl").as_posix(),
            "direct_build": (target / "build_direct.tcl").as_posix(),
            "direct_validation": "Prepared only; template TD build and board verification pending"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("catalog")
    q.add_argument("--examples", type=Path, required=True)
    q.add_argument("--out", type=Path, required=True)
    q = sub.add_parser("audit")
    q.add_argument("--project", type=Path, required=True)
    q.add_argument("--direct-config", type=Path, help="Write direct-flow Tcl configuration from this current .al")
    q.add_argument("--area-option", choices=("-packarea", "-maparea"), default="-packarea")
    q.add_argument("--require-mtbf", action="store_true", help="Fail direct flow if TD produces no usable MTBF report")
    q.add_argument("--fix-hold-high", action="store_true", help="Explicit high hold repair after route; use for diagnosed RTST-5089 abnormal hold paths")
    q = sub.add_parser("verify")
    q.add_argument("--examples", type=Path, required=True)
    q.add_argument("--manifest", type=Path, default=SKILL / "references/baseline_manifest.json")
    q = sub.add_parser("clone")
    q.add_argument("--examples", type=Path, required=True)
    q.add_argument("--demo", choices=DEMOS, required=True)
    q.add_argument("--dest", type=Path, required=True)
    q.add_argument("--manifest", type=Path, default=SKILL / "references/baseline_manifest.json")
    args = p.parse_args()
    if args.cmd == "catalog":
        data = catalog(args.examples.resolve())
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Cataloged {len(data['demos'])} demos -> {args.out}")
    elif args.cmd == "audit":
        data = audit(args.project)
        if args.direct_config and not data["errors"]:
            data["direct_build"] = write_direct_config(args.project, args.direct_config, args.area_option, args.require_mtbf, args.fix_hold_high)
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return bool(data["errors"])
    else:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        if args.cmd == "verify":
            result = {k: verify(args.examples / v["directory"], v["inputs_sha256"]) for k, v in data["demos"].items()}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return any(any(v.values()) for v in result.values())
        entry = data["demos"][args.demo]
        result = clone(args.examples / entry["directory"], args.dest, entry["inputs_sha256"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, ET.ParseError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
