# Issue1: tiny CSI local-clock09 independent route review

2026-10-05. Read-only review: no TD launch, source modification, board action, or other issue investigation. The reports reviewed are from `tools/csi_local_clock09/evidence/td_route_20261005_070137_41408`; source attribution is exclusively `tools/csi_local_clock09/09a_frozen` and `manifest09_first_route.json`, not the changing09b working files.

## 09a result

**09a is not a timing-pass candidate.** Its routed status is SWNS−0.091ns/STNS−0.091ns, HWNS+0.028ns/HTNS0. The single negative path is shared HSx4 sampler-reset release to lane3 PAD.rst recovery. Local-PAD/fabric-PCLK data crossings and both nibble registers are genuinely present and timed, and the problematic PCLK removal paths are positive. The narrow engineering experiment supports this clock topology but cannot certify the complete camera pipeline or analog sampling.

Frozen09a PHY SHA256: `e8be1508d593673991ceb1e36d21029e460c82b20862a999d2b64b6035047b7c`; sampler: `a8161b7d0eae646302e8e4265c90ee63ee8e5ee0b2a96f9ed1f1f1517d25a4d9`; rx clock generator: `3c568be86e4bed43ebab2e5318aced934993ee043b0c7b2137c4c3116034ef13`. The first-route manifest identifies this failed result explicitly. Current working PHY was already changed while this review was performed; its SHA must not be attributed to09a's routed DB.

## Actual IO placement and clock branches

`csi09_route.area` reports seven logical ports/six inputs/one output and twelve physical pads including five implicit differential negative partners. All seven positive/scalar LOCs match the ADC.

| Port | Actual positive/scalar LOC | Implicit negative LOC |
|---|---|---|
| sys_clk | T16 | — |
| checksum scalar uart_tx | U11 | — |
| mipi_clk_hs_rx_p | E13 | F13 |
| data lane0 | C14 | D13 |
| data lane1 | D14 | E15 |
| data lane2 | A15 | A16 |
| data lane3 | G17 | G16 |

All four data pads are HRIO/LVDS18/DDRX2. The UART-labeled output is only a checksum retention sink, not a working serial transmitter. This wrapper must not be downloaded.

Detailed routed paths prove the intended split, beyond merely seeing primitive names in RTL:

- PAD PCLK: E13 clock PAD→DIV2 LCLK at x0y99z0→`clkout`→local `w_pad_clk_x2` net fanout4→four data PAD.ipclk. This path has no GCLK/SCLK intermediary.
- Fabric PCLK: same DIV2 LCLK→`clkdivout`→GCLK at x37y99z17→SCLK→fabric nibble registers, fanout18. Its period is4.488ns.
- Byte: DIV4 LCLK at x0y99z1→`clkdivout`→GCLK at x37y99z16→SCLK→byte/alignment/calibration logic, fanout228, period8.976ns.
- HS sampler: DIV4 `clkout` supplies PAD.isclk and common sampler reset chain, period2.244ns. The related source clock is constrained at2.244668ns and reported with TD's displayed/quantized periods; it has not been relaxed to obtain positive slack.

The clock-utilization report's empty generic local-clock table alone is not sufficient to describe PAD PCLK. The detailed PAD.ipclk launch traces are the decisive evidence of the actual local route.

## Real STA coverage and remaining failure

`td_local09.sdc` creates25MHz system-reference and CSI HS clocks, derives clocks, and only groups the independent system-reference against the complete related CSI family. The exact CSI collection contains parent HS and all four LCLK output branches, with a count assertion. No CSI-to-CSI false path, multicycle, or max-delay exception is introduced. `csi09_exceptions.timing` has no MCP/SMD exception. `check_timing` reports no undefined leaf clock, invalid constraint, disconnected generated clock or combinational loop.

| Routed related path group | Actual analyzed endpoints/paths | Max-check minimum | Min-check minimum |
|---|---:|---:|---:|
| local PAD PCLK→fabric PCLK (raw nibble→n0) | 16/16 | setup+2.744ns | hold+0.036ns |
| fabric PCLK→same fabric PCLK (n0→n1) | 16/16 | setup+3.448ns | hold+0.123ns |
| fabric PCLK→byte (n0/n1→byte) | 32/32 | setup+2.702ns | hold+0.028ns |
| common sampler reset→PAD PCLK | 4/4 | recovery+0.147ns | removal+0.565ns |
| common sampler reset/chain in HSx4 group | 6/6 | **−0.091ns** | +0.279ns including chain data-hold |

PAD-only HSx4 removal is+0.739ns, rather than+0.279ns; the latter includes the chain's own register hold. The whole design's minimum reported removal (including byte/control resets) is+0.077ns. All four PAD PCLK and HSx4 reset checks remain active, including the failing lane3 endpoint.

The exact failing trace is `sampler_reset_sync_reg[2]`→0.298ns net→LUT1 inverter0.097ns→fanout4 reset net0.752ns→lane3 PAD.rst. Reported data delay2.103ns includes the PAD reset model, skew0.192ns, recovery budget2.244ns and default uncertainty0.060ns. This is a genuine slow-corner recovery failure, not a benign unclocked path or missing source constraint. `route.qor` agrees: one violated max endpoint and QOR-1301 explicitly says timing does not meet.

Routed coverage is99.79%, not100%. Four serial data ports have no external input-delay specification, so this experiment cannot demonstrate data-eye margin against the sensor/PCB. The checksum output has no output delay. Constant manual tap0 makes PAD.indly_en appear as dangling nodes; it does not validate dynamic delay loading or auto-calibration scan statistics. `set_param flow bad_qor_check off` permitted the failed route to finish and save evidence; it is not a timing waiver. The09a script did not fail solely because WNS was negative; the explicit failure in the report/manifest must govern acceptance.

## Wrapper validity and limits

The09a wrapper retains all32 raw-byte bits and all32 aligned-byte bits through clocked rotating-XOR sinks, lane-valid acceptance count, best-window/debug outputs and shared sampler-reset observation. The nonzero per-lane/register path counts above show the critical nibble/byte data stages were not optimized away. It is adequate for proving actual-pin legality and the selected clock/reset/data routes in this tiny placement.

It forces manual override at tap0, `wait_for_sync=1` and `packet_done=0`; it contains no genuine CSI packet parser or video/PCIe sink. Its reference is the board25MHz oscillator; main PHY reference is150MHz. In the actual clock detector, LOSS_CYCLES=15M therefore means600ms here versus100ms in main. Neither tiny timing nor source-domain functional checks prove main's control clock timing, its exact timeout behavior, autonomous window search, packet acceptance, complete frame correctness, or the loaded full-design routes.

## 09b logic review performed before its route completed

Working PHY SHA at review: `df203275a110d9889fc027a2a261315f77284f22899ac38e2cd090a56fef3905`. Only the shared reset-chain representation changes in production PHY: old active-low-storage000 shifting1 is replaced with active-high-storage111 shifting0, and outward reset-n is inverted. At every state following reset, new stored bits are bitwise complements of old stored bits. Both expose reset-n sequence0,0,0,1 with deassertion on the third HSx4 rising edge. Asynchronous assertion and the common four-lane release remain the same. PAD primitive still receives `~I_sampler_reset_n`, so the paired inversion can become a direct active-high Q→PAD.rst route. This is logical equivalence of the release event, not proof that TD actually eliminated a LUT or met recovery/removal.

The09b trial wrapper also introduces a25-accepted-byte mock packet handshake to retain dynamic wait-sync/packet-done paths. That is a deliberate wrapper change and must be frozen with its own DB; it is not evidence of real CSI protocol correctness. ADC and SDC are byte-for-byte unchanged from09a. Its Tcl now fails on negative final WNS before matched SDF/netlist export. Exporting files alone will not prove an SDF simulation passed.

At the time of the initial review,09b routing was still pending. Its independent completed-route review follows. Full main-design STA and physical CSI capture remain required.

## Addendum: 09b's own route independently checked

Output: `tools/csi_local_clock09/evidence/td_route_20261005_071009_40084`, report generated07:11:22. This is a separate output/DB from09a. The actual routed status is **SWNS+0.174ns/STNS0, HWNS+0.022ns/HTNS0**. Its confidence is Routed, both slow/fast max/min corners were checked and coverage remains99.79%.

| Related check preserved in09b | Endpoints/paths | Max-check minimum | Min-check minimum |
|---|---:|---:|---:|
| local PAD PCLK→fabric PCLK | 16/16 | setup+2.666ns | hold+0.030ns |
| fabric PCLK→fabric PCLK | 16/16 | setup+3.330ns | hold+0.107ns |
| fabric PCLK→byte | 32/32 | setup+2.661ns | hold+0.022ns |
| shared reset→PAD PCLK | 4/4 | recovery+0.412ns | removal+0.461ns |
| shared reset→PAD HSx4, PAD-only | 4/4 | recovery+0.174ns | removal+0.635ns |

All eight PAD recovery endpoints remain analyzed; their reported slacks are SCLK0.174/0.194/0.211/0.276ns and PCLK0.412/0.432/0.449/0.514ns. All eight PAD removal endpoints also remain analyzed: SCLK0.635/0.674/0.680/0.696ns and PCLK0.461/0.500/0.506/0.522ns. Thus the new positive result did not hide the formerly negative PAD recovery or related nibble crossing.

The worst09b recovery trace is common `sampler_reset_sync_reg[2]` to lane0 PAD.rst: **Logic Level0**, direct FF output→one net fanout5,0.884ns→PAD.rst, no intervening LUT. Data delay1.840ns, clock skew0.190ns,2.244ns recovery budget and0.060ns uncertainty. The physical trace supports the intended inverter removal; it is not inferred only from RTL's double inversion.

The unchanged ADC/SDC hashes still match09a. The new exception report contains no MCP/SMD and check_timing again reports0 invalid/no-clock/disconnected-generator errors. Same serial-input/output-delay omissions and constant-tap indly_en limitation remain. Matched `csi09_phy_sim.sdf` and `csi09_phy_sim.v` are present beside this routed DB; file presence is an export fact, **not an SDF simulation-pass claim**. Source/DB/export freezing is owned by the trial author.

Conclusion: the independent physical review finds no blocking clock/reset/data-STA defect in this09b tiny trial. It validates the candidate topology and synchronous release within this seven-port design. Full-project placement, all main clock/control domains, sensor analog capture, calibration and complete frames must still be checked in the main design and on the board. Neither09a nor09b has been downloaded by this reviewer.
