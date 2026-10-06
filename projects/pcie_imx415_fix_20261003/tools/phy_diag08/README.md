# CSI receive diagnostic08 candidates — issue1 only

Only `cam_video_source.v` and `mipi_csi_rx.v` here are staged production-source candidates. Frozen main FPGA sources, UI/ISP datapath, drivers, boot and the board are untouched. Root integrates these candidates together with ISP's `tools/csi_reset8/csi_rx_phy.v` after checking hashes. The simulation stubs/bench/do files are **not** production sources.

## Interface contract

New cam ports:

```verilog
input  wire [6:0] phy_control_shadow;
output wire [223:0] phy_diag0, phy_diag1;
output wire [31:0] phy_diag0_status, phy_diag1_status;
output wire [31:0] phy_diag0_clock_delta, phy_diag1_clock_delta;
```

`phy_control_shadow` is a user125-domain atomic seven-bit register: bit6 enables external override; bits5:0 are the requested tap. `mipi_csi_rx` accepts that user-domain shadow and uses the unchanged actual `csi_stats_snapshot` to transfer `{185'd0,ctrl7}` as a held coherent bus from `m_axis_video_aclk` into byte clock. No bitwise UI→byte two-FF bus is introduced. Reset asynchronously asserts both sides and the existing snapshot module synchronously releases each side with its own three-FF chain. The command connects directly to PHY's new `I_override_enable` and `I_override_tap[5:0]`.

Command PERIOD125000 is deliberately retained as requested. The existing snapshot request timer lives in its **destination** clock, so it means approximately1.122ms at111.375MHz byte clock, not source-domain1ms. User-domain source cycles remain correctly recorded by that module. A stopped byte clock cannot apply/ack a new command until it resumes.

PHY supplies `O_dbg_raw_bytes[31:0]`, lane0 at low8bits: an unaligned physical sampled byte word, not a decoded packet or a data-valid indication. PHY also supplies `O_sampler_reset_n` from its HSx4 sampler-reset domain. This candidate synchronizes that single status bit through **three ASYNC_REG-marked FFs into byte clock** before putting it in flags; the raw x4 bit never feeds the diagnostic held bus directly. ISP's PHY handles PH1A32-tap interpretation/load pulses, priority over button/auto and unknown X/Z override-enable falling back to auto. These two candidates do not claim to implement or prove physical delay/clock behavior.

## Diagnostic layout

All measurements below originate in the actual byte clock, not UI. Lane/protocol counters and sticky observations reset with PHY's byte `w_reset_out`, increment without `pixel_enable`/`auto_delay_done`/`capture_armed` gating, and wrap modulo32bits. Parser's existing I_enable still controls protocol execution; original calibrated CSI counters and image-enable behavior remain unchanged.

`O_phy_diag0[191:0]` in mipi receiver becomes `phy_diag0[191:0]` through a byte→user held-bus snapshot:

| Bits | Meaning |
|---|---|
| 31:0 | Lane0 aligned-valid cycle count |
| 63:32 | Lane1 aligned-valid cycle count |
| 95:64 | Lane2 aligned-valid cycle count |
| 127:96 | Lane3 aligned-valid cycle count |
| 159:128 | Raw, unaligned physical sampled32-bit byte word |
| 167:160 | Sticky-valid/error observations |
| 174:168 | Applied coherent ctrl7 (enable6/tap5:0) |
| 175 | Byte-domain three-FF synchronized sampler_reset_n |
| 183:176 | Existing dbg_delay byte-domain byte |
| 191:184 | Existing dbg_mipi byte-domain byte |
| 223:192 | Snapshot source byte-clock cycle count |

Sticky byte bits3:0 mean each aligned lane-valid seen; bit4 aligned word-valid seen; bit5 payload-valid seen; bit6 frame-start pulse seen; bit7 packet-error pulse seen. They are observations, not correctness flags. Root should decode control as `(flags >> 8) & 0x7f` and sampler reset as flags bit15 when reading flags32; it must not mistake sampler-status bit7 of the control byte for override enable.

`O_phy_diag1[191:0]` becomes user `phy_diag1`:

| Bits | Meaning |
|---|---|
| 31:0 | Frame-start (w_vsync_out) pulse count |
| 63:32 | Previous frame's observed RAW10 payload-line boundaries, latched on next FS |
| 95:64 | Current observed RAW10 payload-line boundaries |
| 127:96 | Ungated packet-error pulse count |
| 159:128 | Aligned word-valid cycle count |
| 191:160 | Payload-valid beat count |
| 223:192 | Snapshot source byte-clock cycle count |

A payload line is counted on `w_payload_valid && w_payload_last`. A later CRC failure does **not** undo that observation; these are explicitly **not CRC-good/accepted image rows**. At FS the previous count is latched and the current count clears; if FS and payload-last happen on the same event edge, that boundary belongs to the new frame and initializes current count1. The normal parser does not emit that coincidence, but the priority is defined.

The existing original CSI snapshot plus two new diagnostic snapshots all instantiate the unchanged `csi_stats_snapshot` at cam level, source byte clock→destination user clock. Each output status is `{sequence_count[30:0],busy}`, and clock_delta reflects coherent byte-source cycle differences. Default PERIOD12.5M destination clocks means100ms at125MHz user clock. Root owns BAR read registers and command-shadow write/reset behavior.

## Actual ModelSim digital selfcheck

Run only this isolated bench, never include its stub sources in TD:

```text
D:/Modelsim/soft/win64/vsim.exe -c -do E:/.../tools/phy_diag08/selfcheck.do
```

Final actual run `evidence/phy_diag08_20261005_060412_8864/simulation.log` compiled/elaborated with **zero errors and zero warnings**, completed10 explicit checks and383 exact byte-event scoreboard cycles, and exited0. It uses the actual unchanged main snapshot, packet handler and header ECC. PHY, word-alignment, unpack/stream output and ISP/packer/FIFO are deliberately digital/inert stubs; header-exact ISP stubs provide lexical port checking, not ISP processing. Snapshot PERIODs are accelerated only by testbench defparam for simulation; candidates retain their requested production periods.

Coverage includes coherent seven-bit command transfer, PHY input delivery, exact three-edge sampler-status synchronization, partial lane-valid events, parsed FS/payload/packet errors while calibration gate is closed, exact last/current line rollover, user held-bus snapshots/source cycle/status advancement, stopped-byte-clock command stall, asynchronous reset while clock is stopped, synchronous local release and no stale events after recovery, and preserved original calibrated packet counting once calibration resumes. Before calibration, one valid and one CRC-bad line produce two observed payload boundaries and one ungated error, while existing calibrated counters stay0; this specifically prevents mislabelling the new counters as CRC-good rows.

No TD synthesis/STA or analog D-PHY simulation was run; there is no sampler/tap/eye/window/physical frame acceptance from these digital checks. Frozen-source SHA checks and candidate/test evidence are recorded in `manifest.json`; exact diffs are alongside both candidates. Root's combined08 synthesis/STA and physical diagnostics remain required to resolve CSI no-frame issue1.
