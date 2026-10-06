# TD 6.2.2: debugger OOC resets ASYNC_REG visibility parameters

The main build5 has 196 attributed cells after RTL, gate and physical parameter loading, then zero immediately after the second `insert_debugger`. Independent tiny actual TD runs reproduce this and establish a narrower mechanism: **the original attribute set is still retained and becomes visible again by re-enabling the documented global parameters alone.** No explicit `set_property` is necessary for this reproduced case.

No main-project/source change, placement, routing, bit generation or board operation was performed here. The trials compile only an unrelated three-register synchronizer and a debug counter through synthesis and ChipWatcher OOC.

## Final evidence and implication for the running main flow

`evidence/build05_direct_staged.log:2329` reports `phy_parameters count=196`. Lines 2372–2414 run debugger OOC integration; line 2407 explicitly flattens **imx415_pcie_top**, and its main clocks remain visible. The query at line 2419 returns zero. This is not a query stuck on `top_debug_hub`.

Importantly, the main script already re-enables `rtl directive:async_reg on` and `place async_reg on` at lines 2421–2422 before `place`. Check the **post-place** audit before deciding to restart or stamp attributes onto the design: the initial debugger audit was taken before this re-enable and is not by itself proof of missing physical attributes.

The independent fifth actual TD run `evidence/td_async_ooc_trial_fifth.log` records:

| Stage | ASYNC_REG count | Log line |
|---|---:|---:|
| RTL | 3 | 106 |
| Gate | 3 | 314 |
| Second debugger/OOC insertion | 0 | 408 |
| Re-enable documented parameters, before any property setter | 3 | 420/443 |
| Explicit fallback setter, redundant for this trial | 3 | 492 |

The fourth run also showed all three original exact NAME/CLASS/REF_NAME/TYPE objects survived the OOC step, with temporary empty ASYNC_REG lookup values. Its exact-name setter passed, but the fifth run demonstrates that interpreting those empty values as permanently erased metadata would be incorrect. The original attributes are retained behind the disabled/global directive state. The sixth run `evidence/td_async_ooc_trial_sixth.log` proves the specific enable: place-only remains zero (lines 413/415), then RTL directive re-enable restores the original three (422/445), and the preferred setter-free helper verifies the exact set (477). It exits zero with the PASS marker (567). Its fresh output is `evidence/td_async_ooc_trial_20261005_005932_25432`.

The software is proprietary, so this audit localizes the state change to debugger OOC integration and the documented directive enable mechanism; it does not claim to identify a particular internal C++ defect. At the Tcl interface, `info commands current*` is empty, and `*model*` returns only `create_model get_models get_phy_models remove_model` (fifth log lines 411–412). Do not invent Vivado-style current_design/current_model APIs.

## Official mechanism and preservation limits

- Installed official SWUG105 §4.4.8, printed pages 40–41, documents NAME equality filters and says property NAME values belong in the filter, rather than blindly in object-name patterns. Exact equality avoids bus-bracket wildcard ambiguity.
- SWUG106 §4.2, printed pages 30–31, describes global `set_param rtl directive:<name> off` disabling HDL/constraint/Tcl attributes throughout the FPGA flow. §4.3.4, printed pages 37–38, says RTL async_reg is treated as DONT_TOUCH during synthesis and transmitted to physical design. Thus the original RTL-marked chains were protected through gate synthesis; re-enabling the parameter revives that original attribute set.
- SWUG105's MTBF guidance requires both `set_param rtl directive:async_reg on` and `set_param place async_reg on`. Count restoration alone is not a CDC or MTBF pass: placement/route retention and actual timing/chain/clock analysis remain necessary.
- SWUG105 §4.4.13, printed pages 50–51, supports `set_property` on current design objects, but SWUG106 warns that Tcl-only annotation cannot recreate already optimized-away registers. Explicit restoration is therefore retained only as a guarded fallback, and is not recommended for this reproduced parameter-state issue.

Actual TD filter syntax has a pitfall: `NAME == "async_sync_reg[0]"` matches zero because this parser retains quotes as value text; `NAME == async_sync_reg[0]` matches exactly one. The failed third trial records this. The candidate uses unquoted equality values, rejects whitespace/quotes/backslashes/operators in inventory names, and never Tcl-evaluates an inventory name.

## Preferred candidate and root-owned call

`tools/cdc_attribute_restore_exact.tcl` defines inert procedures and does not run TD or mutate any design merely by being sourced. The preferred `cdc_exact_reenable_after_debugger` changes only the two documented enable parameters. It verifies all entries of the exact gate inventory: gate phase/count/true values/no duplicates, unique exact NAME, CLASS=cell, REF_NAME=TYPE=AL_MAP_SEQ, each visible ASYNC_REG value true, and complete visible set identical to the original inventory. It never calls set_property. Missing, ambiguous, wrong or extra objects cause a clear failure, with per-object evidence retained.

For a fresh root-owned full flow, immediately after debugger insertion and before place:

```tcl
source [file join $task_script_dir cdc_attribute_restore_exact.tcl]
insert_debugger
cdc_exact_reenable_after_debugger [file join $task_out cdc_attributes_gate.txt] 196 $task_out
place
```

An already-running full flow that separately performs the same two enables may simply audit the post-place representation and mapped-chain coverage; no restart is implied by the earlier zero-count snapshot. A resume should use the exact preserved gate inventory/checkpoint and fresh output evidence, then verify the enable/set before physical optimization. Merely adding attributes after placement does not establish appropriate synchronizer placement.

The explicit fallback `cdc_exact_restore_after_debugger` remains available only if parameter re-enable demonstrably leaves true property loss and every original sequential object still validates. It restores only the original set and reads back every value/set, with no unrelated watcher objects stamped. A setter or set-comparison failure requires discarding the candidate design. It is not needed for the reproduced OOC case.

All six trial runs preserve their own output directories/logs, including the early read_verilog setup failures and quoted filter failure. Successful fourth/fifth/sixth results are property/API checks, not physical FPGA acceptance. Full root-owned validation still requires the original gate set to remain visible before physical mapping, chain correspondence and mapped attributes through place/route, actual MTBF coverage and valid setup/hold/clock/CDC reports. Raw cell-count equality across gate/PHY is not required because the representation changes.

## Main build physical representation and MTBF tool crash

The completed main `cdc_attributes_place.txt` contains 83 attributed physical cells. `build05_direct_staged.log:3356` reports that count, and the next property report identifies REF_NAME=PH1_PHY_LSLICE and TYPE=AL_PHY_LSLICE (3374–3375), with two internal register settings. Gate cells were AL_MAP_SEQ individual sequentials. Therefore 196→83 by itself is not loss evidence: mapping packs/renames the representation and may name a slice after a different occupant, such as *_syn_2. Verify actual original-chain endpoints/mapped primitive register pins rather than demanding all gate object names still exist unchanged after place.

The same main log terminates with native `Oops! coredump minidump-20261005-005435.dmp` during `report_mtbf -file imx415_pcie_4k_mtbf.rpt -cdc_sink_pin`, after route timing/check/report commands. This is a separate TD executable crash, not a zero-attribute result. It does not supply usable MTBF evidence. Tcl catch cannot recover a process-level native crash. Recommend exporting the routed checkpoint and generating/saving timing-qualified bit outputs before invoking this report, then run MTBF in an isolated TD process importing that preserved checkpoint (a call without -cdc_sink_pin is an investigation candidate, not a proven fix). Preserve crash evidence and state MTBF/CDC acceptance unresolved until a real valid report exists. Do not fabricate a passing report or call every clock crossing safe merely because attributes are visible.
