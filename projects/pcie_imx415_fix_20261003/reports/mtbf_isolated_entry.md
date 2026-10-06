# Isolated TD MTBF diagnostic, pending current build07 checkpoint

No TD process was launched for this tool. Build07 synthesis/placement/routing and its qualification remain root-owned. Do not substitute the earlier build05 database, which failed report_mtbf natively and did not finish its bit outputs.

Installed official SWUG105 §4.9.9 (printed pp.94–95, PDF pp.101–102; `reports/SWUG105_TCL_Command_User_Guide_text.txt:4448`) supports `report_mtbf` after Optimize Placement or Optimize Routing by importing that step's DB. Supported syntax is:

```tcl
report_mtbf [-file <path>] [-nofile] [-no_header] [-append] [-mtbf_warn_below <scientific threshold>] [-cdc_sink_pin]
```

The same installed binary's saved help (`tools/cam27_ip_trial/standalone_setup_help.stdout.log:431`) agrees. There is no documented per-chain selector/current_design/current_model option. The minimum diagnostic is `report_mtbf -file <fresh report>`; it intentionally omits optional `-cdc_sink_pin`, which was present at the earlier native crash. This omission is a diagnostic hypothesis, not a proven TD fix.

`tools/report_mtbf_isolated.tcl` imports the specified PH1A90SEG324 speed2 checkpoint, audits retained physical ASYNC_REG attributes, re-enables the two documented visibility/report parameters and audits again, then calls that minimum report. It never synthesizes, places, routes, modifies constraints, marks additional registers, exports a DB or generates a bit. It does not recompute timing unnecessarily: the manual documents import of the completed placement/routing step followed by report. Setting parameters after import does not establish that the original placement used `place async_reg on`; inspect the same build's original flow log. Gate 196 and physical packed-cell counts need not be equal.

`tools/run_mtbf_isolated.py` validates required explicit checkpoint/bit hashes, common same-build directory/design stem, final `.ts` SWNS and HWNS nonnegative, fresh evidence directory and current root-supplied build ID before launching a separate TD process. Native crashes cannot be caught by Tcl; the launcher preserves stdout, last stage, process result, any real report and before/after hashes of the protected checkpoint/bit/timing files. An isolated timeout terminates only the child it launched. The running main TD flow is never queried or killed.

## Root invocation after qualified current build07

Replace every uppercase token with the actual completed build07 artifact/hash. No default checkpoint is provided; no automatic invocation occurs.

```powershell
D:/Anaconda/python.exe E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/tools/run_mtbf_isolated.py `
  --checkpoint E:/.../CURRENT07/imx415_pcie_4k_pr.db `
  --checkpoint-sha256 ROOT_VERIFIED_CURRENT07_DB_SHA256 --checkpoint-stage pr `
  --qualified-bit E:/.../CURRENT07/imx415_pcie_4k_compress.bit `
  --bit-sha256 ROOT_VERIFIED_CURRENT07_BIT_SHA256 `
  --timing-status E:/.../CURRENT07/imx415_pcie_4k_phy.ts `
  --build-id build07_direct `
  --out E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/evidence/mtbf_isolated07_FRESH_TIMESTAMP
```

For a separately diagnostic current **place** checkpoint use its same-build `*_place.db`, `--checkpoint-stage place`, and the same qualified final bit/timing inputs. A placement report is explicitly placement-stage MTBF evidence, not routed MTBF evidence. Root must confirm the DB stage/provenance; filename checks alone cannot prove DB contents or source association.

The exact child command is:

```text
E:/qianrufpga/TD/bin/td_commands_prompt.exe E:/.../tools/report_mtbf_isolated.tcl
```

**The Tcl path is the sole positional argument. Do not prepend `-tcl` or pass extra Tcl positional arguments to this installed executable.** The launcher supplies script variables through child-only environment entries.

## Interpretation limits

- Native error/crash, zero attributed cells, timeout, missing/empty report or input mutation are unresolved and exit2.
- A real report containing UNDEFINED is retained but unresolved and exits2. Official causes include missing source/destination clock constraints, synchronizer timing violation and zero toggle activity. Default toggle is12.5; the tool does not change activity to force a number.
- A successful nonempty report without UNDEFINED exits0 as **REPORT_GENERATED_REQUIRES_REVIEW**, always with `cdc_acceptance: UNRESOLVED`. Exit0 is execution success, never automatic CDC acceptance. Review actual chains, source/sink clocks, covered/missing crossings, physical placements, MTBF magnitudes/overall result and official warnings. Unknown report formats/no-chain text cannot become a generated CDC PASS; no numeric MTBF is invented.
- The tool adds no false paths, multicycle paths, manual MTBF calculations or unrelated ASYNC_REG properties. A preserved qualified bit does not imply all CDC paths are safe, and a report crash does not invalidate already recorded bit/timing hashes.

## Actual current07 isolated result

Root then supplied and authorized current `evidence/direct_build_20261005_050803_12488`, with routed DB SHA-256 `1b38bd2816c184f1874a5ade062d6e854a14fd94f1c36bc96ca9d0f0257b17f5`, compressed bit SHA-256 `0bf88feca3e60684a2fa18dd1eab7fa72f859f2c32bd4f9181e362224bb7a979` and final SWNS+0.534ns/HWNS+0.021ns. An actual separate TD6.2.2.200067 process imported that routed DB and invoked the minimum report. It **still crashed natively**, even without -cdc_sink_pin. No effective MTBF report or per-chain/overall values were produced; UNDEFINED and actual chain coverage cannot be assessed. This remains UNRESOLVED, not MTBF/CDC PASS.

Fresh evidence is `evidence/mtbf_isolated07_minimal_20261005_forwardslash`. `td.stdout.log:128` records80 imported attributed physical slices and line249 records the same80 after official enable switches. Line286 starts `report_mtbf -file`; the command automatically calls update_timing, which completes with Routed net delay at line305; line309 reports `Oops! coredump minidump-20261005-054300.dmp`. The launcher records Windows process exit3221225477 (access violation), last stage report_mtbf_minimal and no report. It preserves the actual153197-byte dump and logs. DB, bit and final timing hashes are unchanged after the crash. The physical count80 is not proof of80 CDC chains or complete original196-register coverage; physical packing changes the representation.

The first attempt is separately preserved in `evidence/mtbf_isolated07_minimal_20261005_review`: its child never imported a DB because TD interpreted Windows backslashes in the script positional argument as Tcl escape sequences. The launcher now passes forward-slash executable/script/environment paths. Do not misclassify that first CLI-path setup failure as a TD report crash. Both attempts preserve evidence; no output directory was reused.

The same current07 `*_chk.timing` documents no_clock0 and invalid_constraint0, but it is not a full CDC proof. It still reports two HIGH PCIe PLL constraint-vs-primitive frequency mismatches (125MHz constraint versus62.5MHz primitive setting, lines610–617),11 ports without input delay,6 without output delay and3 abnormal PCIe core input-delay groups. External serial/MIPI/hard-PCIe ports require protocol/IP timing interpretation rather than fictitious synchronous delays. Existing async clock groups exclude timing between independent sources and explicitly do not certify every crossing. Original main timing coverage is99.96%; neither positive SWNS/HWNS nor nonzero ASYNC_REG establishes that the remaining CDC/bundled-data/FIFO guards are all verified.

Import/report also re-evaluates the saved SDC. That SDC itself contains a pre-existing absolute-path `open .../evidence/clock_collections.txt w` diagnostic side effect; TD's automatic timing update rewrites that diagnostic clock list, with the same listed clocks. No source SDC or protected DB/bit/timing was edited. Thus “read-only” describes the physical design and protected artifacts, not a claim that proprietary import plus arbitrary embedded Tcl cannot write other diagnostic logs. A future current source flow can scope that audit path to its own evidence directory, but this investigation does not change the saved qualified07 constraints.

Next useful actions are retain the exact crash reproduction for official Anlogic support, inspect whether a current-placement DB produces the same native fault in another isolated invocation if root authorizes it, and continue explicit source-level CDC/guard/clock-boundary audits. Do not add broad exceptions, change switching activity to manufacture a number or use a previous unqualified route/report as replacement certification.
