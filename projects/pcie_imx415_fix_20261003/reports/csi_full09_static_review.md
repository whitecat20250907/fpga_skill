# Issue1: independent full build09 static review

2026-10-05. Reviewer performed only read-only inspection and wrote this report: no source edits, TD launches, SRAM download, sensor acquisition or other board action.

## Decision and provenance

**The full09 CSI receive candidate meets the checked static gate for a controlled SRAM download and complete-frame experiment.** This means its actual final constrained PHY/reset/data routes are positive and preserved in the full design. It does not mean CSI frames, analog sampling, MTBF, all external timing or bidirectional images have passed.

Output: `evidence/direct_build_20261005_071615_17980`. Build stage is COMPLETE, final reports were generated07:41:58 with confidence **Routed**, both slow/fast max/min corners checked. `imx415_pcie_4k_phy.ts`, final timing and route_flow.status agree: **SWNS+0.067ns/STNS0; HWNS+0.020ns/HTNS0; zero failing endpoints**. No negative detailed reported path was found. Place results were treated as temporary and were not used as final acceptance.

Source manifest `evidence/build09_sources.json` SHA256 is `0984970bb9f626f7c572aa8a82cb82a12b998c4a1117a54a9a599fa2f16158cb` (290 input-tree entries). All staged `uisrc`/`al_ip` source and constraint entries match their frozen hashes. Unstaged deploy files, historical logs, readme and managed build entry are not HDL/IP input omissions; they are outside the full-source staging directories. Comparing08/09 manifests finds these five changed entries including version:

| Changed entry | SHA256 |
|---|---|
| uisrc/01_rtl/param_imx415.v | 59f91b28b4330fbe0b694155d13823d5ae5ded3dc0e0e64bd5e72209e0ee01bb |
| uisrc/03_ip/mipi_csi_2/csi_rx_hs_data_phy.v | a8161b7d0eae646302e8e4265c90ee63ee8e5ee0b2a96f9ed1f1f1517d25a4d9 |
| uisrc/03_ip/mipi_csi_2/csi_rx_phy.v | df203275a110d9889fc027a2a261315f77284f22899ac38e2cd090a56fef3905 |
| uisrc/03_ip/mipi_csi_2/rx_clk_gen.v | 3c568be86e4bed43ebab2e5318aced934993ee043b0c7b2137c4c3116034ef13 |
| uisrc/04_pin/imx415_pcie.sdc | d788321f228e648f4ac629602d7d77d8fd6c8e8e4dcf14eede50341c2db1dc22 |

Staged parameter line19 is `PHASE9_VERSION=32'h5644_0901`. Neither the driver nor sensor startup/crop/ISP sources were changed for09 relative to08. Fresh uncompressed bit is4,850,323bytes, SHA256 `f65cfebfbd606f74e3a4e70f02b6439a33d3c8672e4acd39cfd61e04cb54edbf`. The build's selected download output is `imx415_pcie_4k_compress.bit`,2,924,037bytes, SHA256 `82554d7fde3a72545d417813b27fdcbd7fec4a8f3a8ef3f5e6af664f6054b8fc`. Routed DB SHA256 `54e3ce1bca812982d9f1b123d3ec446554a6922ff10e643480d22f0a57541089`; final timing SHA256 `944fa05a58054ad523b32be1dec8a367e0a6db760a7cbf512e2ab519e732d2b5`.

## PHY: final physical topology and checks

The full design preserves the tiny09b topology. `route_clock_utilization.txt` identifies local `w_pad_clk_x2` as LCLK→four PAD clock loads; fabric PCLK is DIV2.clkdivout→GCLK at x37y99z19→SCLK→18 fabric clock loads. Byte clock is DIV4.clkdivout→GCLK at x37y99z18→SCLK branches→1,439 slice and17 ERAM clock loads. Detailed routed PAD-to-fabric launch/capture paths confirm the first branch does not traverse the fabric GCLK. The HS sampler/reset source is DIV4.clkout and remains related to all CSI divisions.

No CSI-to-CSI false path was added to get positive results. The root SDC places the parent HS, PAD PCLK, fabric PCLK, HS sampler and byte clocks in one related CSI group. The following final groups are explicitly reported as Self/Same Domain with real endpoint/path statistics:

| Related group | Endpoints/paths analyzed | Setup/recovery minimum | Hold/removal minimum |
|---|---:|---:|---:|
| local PAD PCLK→fabric PCLK, raw nibble→n0 | 16/16 | setup+2.805ns | hold+0.039ns |
| fabric PCLK→fabric PCLK, n0→n1 | 16/16 | setup+3.197ns | hold+0.165ns |
| fabric PCLK→byte, n0/n1→byte | 32/32 | setup+2.716ns | hold+0.024ns |
| common reset→PAD PCLK | 4/4 | recovery+0.305ns | removal+0.460ns |
| common reset→PAD HSx4, PAD-only | 4/4 | recovery+0.067ns | removal+0.634ns |
| HSx4 sampler status→byte | 1/1 | setup+0.881ns | hold+0.106ns |
| complete byte-domain internal group | 4,951/352,249 | max+1.097ns | min+0.026ns |

All four lanes have both PAD PCLK and SCLK recovery/removal checks. SCLK recovery values are+0.067/+0.169/+0.270/+0.334ns; PCLK recovery values+0.305/+0.407/+0.508/+0.572ns. Minimum removal is+0.634ns against SCLK and+0.460ns against PCLK. The old negative checks were not hidden. Every PAD-reset trace has **Logic Level0**. The global worst max-check path is shared sampler reset to lane2 PAD.rst, slow corner:1.939ns data delay, direct FF output→0.983ns reset net→PAD reset, no inverter LUT. Margin+0.067ns is small and remains conditional on the official device model and specified clocks.

The global worst setup-only path is+0.631ns in the PCIe user domain; global worst hold+0.020ns is a PCIe reorder-RAM address path. Minimum reported removal+0.021ns belongs to debugger/PCIe control resets, not PAD removal. This distinction avoids attributing whole-design minima to the wrong PHY check.

## Synchronizer attributes through debugger insertion and mapping

`cdc_attributes_rtl.txt`, gate and phy_parameters each record232 attributed logical gate objects. Immediately after debugger OOC insertion the getter reports0, but the documented RTL/place parameter re-enable exposes the **same exact232 original AL_MAP_SEQ objects**, all ASYNC_REG=1; `cdc_exact_after_reenable.txt` has validated_count232/problem_count0. The exact helper compares the entire set and performs **no set_property repair/fabrication** on this successful path.

Place and route each record104 attributed **physical mapped cell objects**, with the same inventory. This is a separate granularity; it must not be reported as232 placed cells or interpreted from count alone as128 lost FFs. Concrete retained objects include CSI `hs_reset_sync_reg[1]_syn_2`, `sampler_reset_sync_reg[1]_syn_2`, byte sampler-status synchronization, clock-detector Gray/enable synchronization, original CSI and diagnostic snapshot request/ack/reset cells, and command-mailbox synchronization. Gate exact-preservation and physical attribute visibility are proven facts; full per-FF packing equivalence or MTBF is not inferred from a nonzero count.

The actual build declares `DIRECT_BUILD_CDC_STATUS=MTBF_PENDING_ISOLATED_REPORT`. There is no fresh MTBF certificate in this output. A successful attribute audit or constrained STA is not a quantitative CDC/MTBF pass.

## Native warnings: retained and bounded, not silently waived

### PHY-5049: two clkdivout nets without buffers before mapping

The warning text itself says a GCLK is automatically created. Actual final route reports show DIV2 and DIV4 clkdivout each driving their automatically created GCLK/SCLK trees. Thus this pre-place absence is resolved for the final relevant fabric branches by physical evidence; the local PAD-PCLK branch deliberately remains local. SYN-6021 and SYN-6024 counts are0 in this build. This does not waive future changes that could alter those branches.

### PHY-5016: six PLL-to-IO location warnings

These occur during Pre-Place DRC and contain no instance or port names. Same counts occur in07/08, but historical frequency is not a correctness argument. Final `imx415_pcie_4k_phy.area` reports all20 general physical pads with locations and correct standards; hard PCIe pins are also fixed by the actual native core. Relevant final camera pins are clock E13/F13, data0 C14/D13, data1 D14/E15, data2 A15/A16, data3 G17/G16, MCLK A18, XCLR B18, SCL B14 and SDA A14. Ref clock T13/T14, system clock T16, UART V11/U11 and PERST U14 also have actual locations. No unnamed/unplaced external IO appears in that final table.

This establishes final physical IO placement. The six unspecific messages cannot be individually attributed from the transcript, so they remain documented rather than declared formally eliminated. Correct LOC does not prove external clock waveform, board routing, electrical levels or sensor rails.

### PHY-5060: one mixed27MHz clock/data fanout

The native critical warning identifies `u_camera_clock_startup/clock27`,72 pre-map clock loads and one data/control input `cam_mclk_syn_3.b`. This is the intentional forwarded MCLK AND input, driven by a gate enable registered on the falling27MHz edge. Final clock report has27MHz PLL.clkc[1]→`bufg_output27` GCLK at x37y99z2,54 clock loads plus one data/control load; the final output IO `cam_mclk` is A18/LVCMOS18/drive8. Staged top connects the startup's sensor_mclk directly to that port. The warning remains and has not been suppressed.

No `cam_mclk` endpoint is present among the final timing report's detailed paths; internal gate sequencing/IO LOC and an internal frequency monitor do not certify the waveform at A18/sensor INCK. Scope-level pulse widths, duty cycle, reset truncation and board electrical confirmation remain outside this review. PLL analog lock/rail timing is likewise not proven by static timing.

### Other final timing boundaries within issue1/issue10

`check_timing` reports coverage99.96%, zero undefined leaf clocks/invalid constraints/disconnected generated clocks/combinational loops, and both CSI LCLK frequency checks match their settings. It also retains two high-severity **PCIe PLL setting mismatches**:125MHz constraints versus62.5MHz configured-model reference/output frequencies, eleven missing external input-delay specifications, six missing output-delay specifications, three abnormal native PCIe input-delay constraints, and unused/dangling native nodes. These must remain in the complete timing record; positive WNS does not prove complete external timing or settle the PCIe core's frequency model.

Final routing DRC retains RTCLK-5078 warnings for locally routed generated I2C SCL and debugger JTCK. These clocks are still constrained and their real related paths contribute to final STA. No false path was added to clear their timing. This review does not claim those warnings disappear, nor broaden current issue1 into a new source change.

## What the next board experiment must establish

Use the exact frozen09 version/bit, confirm actual version0x56440901 after SRAM download, then obtain independent diagnostic snapshot bookends, lane/word/payload/FS activity, genuine calibration-window information and complete correctly sized frame capture. Manual override can aid diagnosis but must not be reported as a successful auto-calibration window. This reviewer authorizes no separate operation; root owns the already authorized board experiment.

Until physical acquisition passes, issue1 remains unclosed. Complete timing/MTBF/electrical qualifications retain the limitations listed above. No statement about bidirectional-image success or repaired unrelated issues is supported by this static review.
