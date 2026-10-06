# FPGA5 final timing audit and independent sampler candidate

This directory is an independent proposal only. No file under `fpga/`, no SDC, no driver, no board, and no TD database was modified for this audit. The frozen full-route source remains the test baseline. No CRC/header/payload pipeline was added because the actual final report does not identify such a failing path.

## Actual final route evidence

`evidence/direct_build_20261005_002919_8820/final_timing.rpt` is Routed, both slow/fast corners, 99.96% STA coverage, report scheme 10 end points per group and 1 path per endpoint. Global setup/recovery WNS = -1.960ns, TNS = -7.222ns; hold WNS = +0.020ns, TNS = 0. The four reported negative endpoints account for the complete negative TNS:

| Sink | Check | Slack ns |
|---|---|---:|
| `mipi_data_hs_p[2]_syn_2.rst` | recovery | -1.960 |
| `mipi_data_hs_p[3]_syn_2.rst` | recovery | -1.881 |
| `mipi_data_hs_p[1]_syn_2.rst` | recovery | -1.707 |
| `mipi_data_hs_p[0]_syn_2.rst` | recovery | -1.674 |

All launch from `.../u_csi_rx_phy/hs_reset_sync_reg[1]`, clocked by the **byte** clock, and end on the four **HS** IDDR reset pins. The report treats the 4:1 related clocks as Same Domain, with only 2.244ns until the next HS edge. The reset register has fanout 653; the worst path has 2.186ns delay and 1.978ns launch/capture clock skew. It traverses a fabric inverter into an IO primitive. It is an actual asynchronous-reset recovery requirement, not a CRC data-path failure and not a CDC that may simply be false-pathed.

The byte domain itself has setup +1.438ns / hold +0.028ns, 0 violating endpoints and Fmax 132.661MHz. User125 has setup +0.382ns / hold +0.020ns. Byte-to-nibble and nibble-to-byte also pass. Clock-summary byte frequency is 111.408MHz, HS445.633MHz, from rounded SDC period2.244ns; the intended sensor891Mbps/27MHz family is byte111.375MHz / HS445.5MHz. This small rounding cannot explain a 1.960ns deficit. Do not reduce the clock, invent a multicycle or exclude a related-domain recovery to obtain a green report.

`timing_audit.json` records the four exact path headers and frozen PHY source/candidate hashes. This analysis explains the reported negative endpoints; 99.96% coverage still requires independent examination of the unreported 0.04% and all warnings. Positive byte timing is evidence for this route, not a guarantee for a future route.

## Actual primitive reset semantics

Local primary sources:

- `E:/qianrufpga/TD/doc/UG910_PH1A_Libraries_Guide_for_HDL_Designs.pdf`, printed pp9-10: PH1_LOGIC_IDDRx2 is a 1:4 sampler, external pclk = sclk/2; ASYNCRST permits ENABLE/DISABLE.
- `E:/qianrufpga/TD/sim_release/ph1/ph1_logic_io.v`, lines381-429: `rst_node = (ASYNCRST=="ENABLE") ? rst : 1'b0`; DISABLE **ignores the external rst**, it does not implement synchronous reset. Global GSR remains in the model. The x2 sampler contains only sclk sampling registers and pclk deserialization registers. It contains no free-running divide/phase counter; pclk is supplied separately.
- `rx_clk_gen.v` owns the existing DIV2/DIV4 LCLK phases and its reset remains unchanged. `csi_rx_byte_align.v`, parser, calibration, FIFO and new-FS gating retain their resets.

A new ordinary fabric synchronizer running at HS is an alternative to test, but it may route HS through GCLK before returning to the IO pin and still fail recovery on both DDR edges. A negedge release leaves only half a 445.5MHz cycle to the rising sampler edge. Neither is automatically a reliable timing fix. Local clock/placement availability and both edge checks must be proved if that alternative is chosen.

## Minimal independent candidate

`csi_rx_hs_data_phy.v` changes only the PH1A sampler primitive: `ASYNCRST("DISABLE")`, `.rst(1'b0)`. It samples continuously; the byte-domain control/reset rejects unqualified data and recalibrates before capture/new FS. All serial ordering, IDELAY width/taps, pclk/sclk, nibble assembly, byte registers, latency, interfaces and PH2 branch retain their original bytes. `csi_rx_hs_data_phy_reference.v` is an exact frozen original renamed only to instantiate both in a test.

There is **no promise that raw sampler outputs are zero while user reset is asserted or immediately after release**. Register contents are overwritten by incoming samples. The test conservatively excludes the first eight byte clocks from equivalence and explicitly verifies downstream byte-align reset and zero-stream settling. Production must keep calibration/valid/new-FS qualification; this candidate must not be copied into a design that consumes unqualified first raw samples as pixels. It also does not resolve bit sampling, IDELAY quality, interrupted HS burst phase, external PHY timing or Bayer coordinates.

This removes an unnecessary external asynchronous-reset path by design. It is not a false-path exception. It does not change the legal 891Mbps requirement or mask runtime errors. No new LUT/register/ERAM storage or steady-state latency is added. Future TD must verify the IO rst is constant, all remaining sampler/data/related-clock setup/hold/recovery checks pass, and no unreported reset requirement appears. Board acceptance must repeat calibration, active CRC/ECC/WC/overflow counters, short/long clock-loss recovery, first complete frame and sustained colour/image tests.

## Actual digital selfcheck

Run:

```powershell
& 'D:/Modelsim/soft/win64/vsim.exe' -c -do 'E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/tools/csi_fast6/sampler_reset.do' -l 'E:/qianrufpga/fpga-lab/projects/pcie_imx415_fix_20261003/tools/csi_fast6/evidence_sampler6.log'
```

The test compiles the **actual TD PH1_LOGIC_IDDRx2 / IDELAY / GSR models**, actual byte_align and both source variants. It uses four independent serial lanes at a true 4:2:1 clock ratio. Exact unchanged primitive equivalence covers 3828 byte-clock samples (2964 nonzero), 844 qualified lane-byte/valid comparisons after align settling, 12 resets including releases in all eight serial-bit phases and sub-byte-clock pulses, five stopped-clock/restart cases, and downstream byte-align asynchronous reset and zero-stream flush. Clock-stop tests freeze all related phases; they do not simulate a real LCLK restart or electrical LP/HS transition.

Result: ModelSim RC0, compile/simulation 0 errors / 0 warnings; `PASS CSI_FAST6_SAMPLER_ALL_DIGITAL_CHECKS`. Logs remain under `evidence/sampler_20261005_044754_11352/` and `evidence_sampler6.log`. An intentionally over-strict preliminary assertion also compared inactive shifted-byte values and failed at age64 with both valid vectors0000; `evidence_sampler6_inactive_negative.log` is preserved. The aligner retains its last offset until a new sync, so inactive bytes have no interface meaning. The final TB still checks exact valid vectors and every qualified lane byte, rather than relaxing a valid-byte mismatch. This also documents that early reset-free raw content is not guaranteed zero. Existing `tb/csi_calibration.do`, `tb/csi_capture_gate.do`, `tb/csi_integrity.do` supply additional calibration/manual/reset/new-FS/protocol proofs; their PHY shells do not prove this IDDR change. No old gate/RAW test is presented as a new electrical or colour test.

No candidate TD implementation or board test was run here. Parent chooses whether to integrate this proposal and runs a fresh full build/physical acceptance. CRC/header/payload pipelining is deliberately deferred: the current actual route has margin and protocol feedback (`packet_done/sync_wait` to byte_align) means any extra latency requires latency-aware goldens and fresh route evidence.
