# PH1A90 routed PHY simulation: installed TD 6.2.2 evidence

Scope: issue 1 only, PHY09 local PAD PCLK / global fabric clock candidate. Read-only research completed 2026-10-05. No TD process, ModelSim compilation, source change, or board operation was performed for this research. The commands below now have actual PHY09b export evidence from the ISP/root-owned TD run, but are not a simulation PASS.

## Official installed references

- `E:/qianrufpga/TD/doc/SWUG/SWUG105_TCL_Command_User_Guide.pdf`, section 4.3.7/4.3.8, printed pages 31/32 (PDF pages 38/39): `write_verilog [<file_path_name>]`; `write_sdf [-check_corner <SLOW/FAST/SLOW_FAST>] [-file <file_path_name>]`. `SLOW_FAST` is the documented default corner. Use the documented `-file` form, despite the example showing a positional SDF filename.
- `E:/qianrufpga/TD/doc/SWUG/SWUG107_Design_Simulation_User_Guide.pdf`, printed pages 8-14 (PDF pages 11-17): open a completed Optimize Routing run, select **Tools > Project Simulation > Post Route Simulation > Timing Simulation**; TD creates a matching netlist, SDF, testbench and simulator do file. This is the documented GUI route if the command-line export cannot be verified.
- The same installed TD executable help was previously captured in `tools/cam27_ip_trial/standalone_setup_help.stdout.log`: line 182 includes `write_verilog ... -implement ... -sdf <string> ...`; line 217 includes `write_sdf ... -check_corner <string> ... -file <string>`.
- Read-only inspection of `E:/qianrufpga/TD/bin/td_commands_prompt.exe` finds the GUI export templates `write_sdf -file "%1"` and `write_verilog -sdf "%1" "%2"`, with neighboring `_pr.db`, `*_phy_sim.v`, `*_phy_sim.sdf`, and Timing Simulation strings. The `-sdf` filename therefore precedes the output Verilog filename. The ISP/root-owned 09b run actually executed this CLI recipe successfully; the concrete export validation is recorded below. No undocumented meaning is assigned to `-implement`; it is not needed in this timing-simulation recipe.
- `D:/Modelsim/soft/docs/pdfdocs/modelsim_se_ref.pdf` (ModelSim SE 10.5), PDF pages 930/931: `-sdfmin`, `-sdftyp`, `-sdfmax [<instance>=]<sdf_filename>` choose the SDF triple entry; `-sdfnoerror` downgrades errors and `-sdfnowarn` hides warnings. Do not use either for this validation.

## Export from the actual PHY09 routed checkpoint

Run in an isolated output directory with a verified **PHY09** routed checkpoint and unchanged source/constraints provenance. Do not reuse 07 route evidence to certify 09, or use 08's failed route as a qualified candidate. Use the sole Tcl positional argument convention already established for this TD binary; no `-tcl` argument.

```tcl
# Values must be filled with the root-owned PHY09 paths, not historical DBs.
import_device ph1_90.db -package PH1A90SEG324 -speed 2
import_db E:/.../phy09_pr.db
update_timing -mode final
write_sdf -check_corner SLOW_FAST -file E:/.../phy09_phy_sim.sdf
write_verilog -sdf E:/.../phy09_phy_sim.sdf E:/.../phy09_phy_sim.v
```

```powershell
& 'E:/qianrufpga/TD/bin/td_commands_prompt.exe' 'E:/.../export_phy09_sim.tcl'
```

All TD paths must use forward slashes. This import/export flow must not run synthesis, place, route, fix_hold, bitgen, alter constraints, or overwrite the checkpoint. Hash the checkpoint before/after and save exporter exit code/log. If TD cannot export a matching physical netlist, use the official GUI route above and retain its generated do file; do not replace the physical clock/PAD models with a hand-written ideal model.

## Actual installed PH1 simulation libraries

The PH1 family is **SALPHOENIX1A**, not PH1P or PH2 (SWUG107 device-family compiler table, printed page 6). Use libraries from this exact installed TD version; rebuild compiled libraries after changing TD or ModelSim version (SWUG107 printed page 5).

Directories:

- `E:/qianrufpga/TD/sim_release/common/*.v`
- `E:/qianrufpga/TD/sim_release/common/apm/*.v`
- `E:/qianrufpga/TD/sim_release/ph1/*.v` and `*.sv`

Relevant models include `ph1_phy_pad.v`, `ph1_phy_lclk.v`, `ph1_phy_lclk_v2.v`, `ph1_phy_gclk.v`, `ph1_phy_gsr.v`, and `common/al_phy_glbl.v`. Several PH1 models use IEEE-1735 protection with Mentor keys. An encrypted-model compilation or elaboration failure is a validation failure; do not substitute a zero-delay stub. `TD/arch/ph1_macro.v` is a synthesis macro declaration source and is not the routed simulation library.

SWUG107 figure 4-5 requires both global modules for PH1. For a generic netlist without built-in globals, instantiate them in the TB with these exact instance names:

```verilog
PH1_PHY_GSR PH1_PHY_GSR();
glbl glbl();
```

or load them as additional simulator top levels. Do not do both. **The actual 09b exporter already instantiates `glbl glbl()` inside the DUT at line 13234 and drives it from `PH1_PHY_GSR` at lines 13236-13239. For this netlist, load only `PH1_PHY_GSR` as an additional top; do not create another glbl.** The PAD model references `PH1_PHY_GSR.done_gwe` at `ph1_phy_pad.v:861`; common mapped sequential models reference `glbl.done_gwe`. The official TB rule is to initialize every input and start the clock sources **after GSR has released**. The PH1 GSR release is not assumed from an arbitrary fixed wait; wait on the actual model's release state, with a bounded watchdog. `al_phy_glbl.v:23-46` declares its own global state and startup sequence; the PH1 global behavior is encrypted.

## ModelSim do recipe

Execute in a new simulation directory. The following separate-library recipe implements the same library mapping as SWUG107 figure 4-9; figure 4-10 permits compiling raw library sources into work instead. Only one of those methods should be used. Compile the actual routed netlist and self-check TB, never the old behavioral PHY stub.

```tcl
onerror {quit -code 1 -force}
vlib work
vlib common
vlib ph1
vmap work ./work
vmap common ./common
vmap ph1 ./ph1
set tdlib E:/qianrufpga/TD/sim_release
vlog -work common {*}[glob $tdlib/common/*.v]
vlog -work common {*}[glob $tdlib/common/apm/*.v]
vlog -work ph1 {*}[glob $tdlib/ph1/*.v]
vlog -sv -work ph1 {*}[glob $tdlib/ph1/*.sv]
vlog -work work E:/.../phy09_phy_sim.v
vlog -sv -work work E:/.../tb_phy09_routed.sv
# Actual 09b netlist has its own initial $sdf_annotate and glbl instance.
# Do not add an external -sdfmax/-sdftyp/-sdfmin annotation as well.
# -novopt avoids the observed encrypted native-model vopt stall.
vsim -novopt -t 1ps -L common -L ph1 +maxdelays \
    +sdf_verbose +delayed_timing_checks +ntc_warn \
    -sdfreport=E:/.../sdf_annotation_max.rpt \
    work.tb_phy09_routed ph1.PH1_PHY_GSR
run -all
# TB must finish with $fatal on failure and an explicit all-checks PASS on success.
quit -code 0 -force
```

```powershell
& 'D:/Modelsim/soft/win64/vsim.exe' -c -l 'E:/.../simulation_max.log' -do 'E:/.../run_phy09_max.do'
```

Repeat in fresh simulator runs with `+typdelays` and `+mindelays`, saving each annotation report and simulation log. These are **plus** options, not `-mindelays`. ModelSim SE User Manual PDF page 1301 explicitly states that an omitted `$sdf_annotate` `mtm_spec` defaults to `tool_control`, which uses command-line `+mindelays`, `+typdelays`, or `+maxdelays` (default typical). Thus the actual 09b one-argument `$sdf_annotate` call is controlled by these options without a derived netlist or duplicate injection. Reference Manual PDF pages 873/950 says `-novopt` is needed if a different vopt delay selection would otherwise take precedence. This is documentation of corner selection, not a completed simulation result.

The TD `-check_corner` process-corner setting and ModelSim min/typ/max triple selection are different controls. Read the exported triples; do not assume a particular slow/fast-to-triple mapping if the exporter does not document it. For a different exported netlist **without** a built-in `$sdf_annotate`, external `-sdfmax /tb/u_dut=file` is the documented alternative; never apply both methods to the same 09b DUT.

Do not compile with `+nospecify` or invoke `+notimingchecks`/`+notimingcheck`. Negative timing checks are enabled by default; retain `+delayed_timing_checks +ntc_warn`, and do not use `+no_autodtc` or `+no_neg_tchk` to zero them (ModelSim User Manual PDF pages 277-287). Do not use `-sdfnoerror`, `-sdfnowarn`, or an SDF fallback-to-primitive option to conceal an incompatible netlist/library. `ph1_phy_pad.v:865-907` contains clock/data IOPATH, recovery, and removal specify arcs; lines 911 onward contain setup/hold checks. Their source default values are zero. **Only successfully annotated nonzero routed delays are routed evidence.**

## Required evidence before claiming B8/packing validation

1. Fresh exported physical cells include actual PH1 PAD and local/global clock resources. The SDF header DESIGN and instance hierarchy match that netlist and the chosen DUT annotation point. Files are nonempty and retain source/checkpoint/export hashes.
2. Annotation reports show the actual CSI clock/PAD instances and nonzero clock insertion/interconnect/IOPATH values. Missing instance, unsupported cell, unmatched timing arc, or missing relevant delays is unresolved, even if the TB prints PASS. This also applies if encrypted LCLK behavior cannot be elaborated.
3. Use external clock/data stimulus and the actual PLL/local/global model, with correct frequency and reset/GSR startup. Do not force the internal clocks or replace local/global clock resources with direct wires. Explicitly compare raw lane byte order and repeated `8'hB8` plus nonrepeating payload byte sequences to expose edge/order changes.
4. Sweep input data phase relative to the received clock across the defined safe setup/hold window, and exercise startup/reset/recovery. Log every phase/corner result and all timing-check violations. A violating stimulus phase may characterize the boundary; it cannot establish a usable operating region. Byte-count-only checks are insufficient.
5. Routed STA for the same PHY09 candidate must separately pass the PAD reset recovery/removal and data paths. Simulation does not replace STA or certify the real sensor's analog eye opening. A routed narrow test validates the modeled candidate packing and delays; the full top and board must still be separately tested.

## Actual PHY09b export audit (2026-10-05)

Actual ISP/root-owned TD output:
`tools/csi_local_clock09/evidence/td_route_20261005_071009_40084/`.
The source manifest is `tools/csi_local_clock09/manifest09b_frozen.json`; the audit read the original emitted files without editing them. `td_route09b_launcher.log:1409-1412` records the exact successful `write_sdf` followed by `write_verilog -sdf` commands. Netlist/SDF both identify `td_local09_top`, `Release_2026.1_SP2`, and the same one-second export interval. The SDF time unit is 1 ps and Verilog precision is 1 ps.

| Original artifact | Bytes | SHA-256 |
|---|---:|---|
| csi09_route.db | 748152 | 9e16ac093629873f7c8872fcb918c02996f1b729659f3d4e677593c738088684 |
| csi09_phy_sim.sdf | 657832 | cafdf6ddee0741dedaef089c613d3c2f02fe3bf8d7bc383b9443bf17e6a11168 |
| csi09_phy_sim.v | 658466 | ed6e8e4711312479201f8ac7f5309b65a37d5b03be692614b83bbc37ea782ffe |
| csi09_final.ts | 62 | e5900966d10af15e7857dd87de62d4bc45b386f42d979c6aff35e843869962e5 |

Static matching results are saved in `reports/phy09b_sdf_export_static.json`:

- 506 non-top SDF CELL records all match an actual exported instance and its physical primitive type, **0 missing/mismatched**.
- 2573 INTERCONNECT records have both endpoint instance names and connected port names present in the netlist, **0 undeclared endpoints**.
- SDF contains 1877 IOPATH, 248 RECREM, and 1112 SETUPHOLD records.
- Netlist has 513 physical instances: 490 LSLICE, 12 PAD, 3 GCLK_V2, 3 SCLK_V2, 2 LCLK_V2, 2 HR_BANKREF, and 1 CONFIG_V2. SDF covers 7 PAD. The five additional PAD instances are visibly unconnected complementary LVDS pins (`*_syn_3`, Verilog lines 1864/1909/1954/1999/2044), and the two HR_BANKREF are configuration resources; these seven have no CELL timing record. This is a specific structural exception, not a reason to ignore missing timing on connected CSI pins.

Nonzero timing examples (all values in ps):

| Source location | Actual routed delay |
|---|---|
| SDF lines 2612-2618, MIPI clock PAD `ipad -> di` | 331:350:350 |
| SDF lines 2621-2691, four CSI data PAD `posedge ipclk -> diq[0..3]` | 235:269:269 |
| SDF lines 4779-4786, local LCLK_V2_0 `clkin -> clkdivout`, `clkin -> clkout` | 275:309:309; 621:707:707 |
| SDF lines 4789-4796, local LCLK_V2_1 corresponding arcs | 275:309:309; 345:398:398 |
| Root interconnect, MIPI clock PAD `di -> LCLK_0/1.clkin` | 53:60:60 |
| Root interconnect, LCLK_0 `clkout -> PAD lane0.ipclk` | 601:671:671 |
| Root interconnect, LCLK_1 `clkout -> PAD lane0.isclk` | 601:671:671 |
| Root interconnect, LCLK_0/1 `clkdivout -> fabric GCLK` | 936:1042:1042 |
| SDF lines 5451-5476, three fabric GCLK_V2 `clkin[0] -> clkout` | 277:323:323 |

Connected data PAD `ipclk` uses `phy/w_pad_clk_x2`, whereas `isclk` uses `phy/w_hs_clk_x4` (Verilog lines 1878-1908 and other lanes). The local sampling path therefore survives real export separately from the fabric GCLK path; it is not an ideal wire model.

Exact primitive source files exist in the installed PH1 simulation release for all seven primitive types. LCLK_V2 and SCLK_V2 are encrypted, so their module bodies cannot be verified by text parsing; actual compiler/elaboration compatibility remains for ISP's simulation. CONFIG_V2 requires `ph1_phy_config_v2.sv`, which a `.v`-only library glob misses. PAD additionally instantiates PH1 logic IDDR/delay models; compiling the full same-version common/apm/ph1 release avoids the incomplete old native-model-only do file.

The netlist **line 510 embeds `initial $sdf_annotate("<exact absolute emitted SDF path>");`**. Keep that path available and the original netlist unchanged. Do not simultaneously apply an external SDF. It also embeds glbl at line 13234 as explained above.

PAD checks include `SETUPHOLD 1041ps/-865ps` and `RECREM 761ps/-545ps`. ModelSim User Manual PDF page 1305 explicitly permits SDF RECREM matching separate `$recovery` and `$removal`; the PAD source using separate checks is not itself evidence of incompatibility. Check actual annotation and `+ntc_warn` for negative values being forced to zero, nonconvergence, or unmatched arcs. No such runtime outcome is claimed by this static audit.

The tiny 09b final timing file records SWNS +0.174 ns, HWNS +0.022 ns, both TNS zero. This is narrow-project STA evidence only. At this audit's completion the **SDF simulation, full-top STA and board B8/frame capture are not certified**; ISP is running separate real annotation tests. Static export matching is now verified; it is not a waveform/packing PASS.
