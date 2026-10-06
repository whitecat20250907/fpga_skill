# Build08 gate audit: CSI no-frame issue only

Read-only audit of the running root-owned `evidence/direct_build_20261005_061224_37468` and `evidence/build08_direct_staged.log`. No TD process was started, no source/constraints/drivers were edited and no board was accessed. Build08 has entered placement; this is **gate-stage evidence, not routed timing or physical frame acceptance**.

## Actual retained registers

`cdc_attributes_gate.txt:181–183` records all three `u_cam_video_source/u_mipi_csi_rx/phy_sampler_reset_sync_reg[0..2]` with ASYNC_REG=1. Lines186–188 record all three `u_cam_video_source/u_mipi_csi_rx/u_csi_rx_phy/sampler_reset_sync_reg[0..2]` with ASYNC_REG=1. The gate inventory has232 attributed sequential cells.

The second debugger/OOC step temporarily hides the global attribute view (`build08_direct_staged.log:2528`, count0). The already-running builder then re-enables the documented RTL/place switches and verifies the exact original set. `cdc_exact_after_reenable.txt:181–188` identifies the six objects as CLASS=cell, REF_NAME=TYPE=AL_MAP_SEQ and ASYNC_REG=1. Its final `validated_count=232` and `problem_count=0` prove that the intended gate objects survived and were visible again before placement. This is not a complete CDC/MTBF proof, nor a reason to stamp additional registers.

## Related clocks and actual reset timing paths

The applied SDC and actual PCIE_FIX_CLOCKS entries keep the MIPI parent, x4 `U_io_clk_div_0.clkout`, x2 `U_io_clk_div_0.clkdivout` and byte `U_io_clk_div_1.clkdivout` in one related-clock group. UI/system/PCIe groups remain independent; no new false path or async split of x4/x2/byte was introduced.

Actual `imx415_pcie_4k_gate.timing` evidence:

| Evidence | Meaning |
|---|---|
| 11355–11356 | PHY sampler FF2→lane3 PAD.rst, x4-clock recovery check, slack+0.058ns |
| 11415/11475/11535 | Same sampler FF2 release drives lane2/lane1/lane0 PAD.rst recovery paths |
| 11595–11596 | PHY sampler FF0→FF1 data path clocked on x4 |
| 11652–11653 | PHY sampler FF1→FF2 data path clocked on x4 |
| 11989–11990 | PHY sampler FF2→diagnostic sampler FF0, x4→byte setup check |

The latter group is explicitly reported `Type: Same Domain` and has setup slack+1.469ns. It is a real related-clock checked path, not an unexamined crossing discarded by async grouping. The gate report also identifies the four sampler PAD registers' `isclk` as x4 and shows the sampler release inversion/common fanout to those reset inputs. The shared sampler reset therefore reaches actual PAD register reset endpoints at gate stage.

Gate recovery margin+0.058ns is small; final placed/routed recovery/removal/setup/hold timing remains necessary. Gate net-delay estimates are not a routed certificate. The broader gate design still has estimated setup violations (e.g. user-clock AWB path−1.379ns); those estimates must not be confused with final route failure or success.

## CSI pad assignment evidence and limits

Root log1084–1089 shows actual execution of CSI constraint assignments, rather than merely their presence in a source ADC:

| Port | Requested location | Standard |
|---|---|---|
| mipi_ref_clk_p | T13 | LVDS18 |
| mipi_clk_hs_rx_p | E13 | LVDS18 |
| mipi_data_hs_p[0] | C14 | LVDS18, INDEL20 |
| mipi_data_hs_p[1] | D14 | LVDS18, INDEL20 |
| mipi_data_hs_p[2] | A15 | LVDS18, INDEL20 |
| mipi_data_hs_p[3] | G17 | LVDS18, INDEL20 |

The gate timing paths explicitly show `port E13 ... mipi_clk_hs_rx_p` (e.g.line11369) and `port T13 ... mipi_ref_clk_p` (e.g.line3281). Four data inputs do not have matching external input-delay paths in the normal ten-endpoint-per-group report, so this report does not print their port locations. Its standard gate area table counts20 PADs overall but is not a per-pad assignment listing. The gate reset paths prove all four CSI data PAD register endpoints exist, while **final per-data-pad LOC mapping must still be confirmed from the placement `report_area -io_info`/final native log or a root-owned exact query**. No extra TD invocation was made to obtain a premature physical table.

## Warning counts at this audit boundary

The flushed root stdout transcript has zero occurrences of SYN-6024, SYN-6021 or `unassigned`. Initially native logs were zero-byte/pending; while finishing this audit they flushed: actual `td_20261005_061224.log` is493031bytes/4963lines and `.logw` is117125bytes/800lines. Both were then read independently and each contains **zero SYN-6024, zero SYN-6021 and zero unassigned warnings** at the flushed boundary. A case-insensitive numeric6024/6021/unassigned search also found none. This is now actual current-run native evidence, not an inference from empty files. The process is still running; later final native/placement checks remain required.

Existing vendor PCIe width/hardwired-port and top implicit-wire declaration warnings are present, but this limited audit introduces no changes or work on other issues. Final acceptance for issue1 requires completed08 placement/routing constraints/PAD mapping and actual byte/raw/calibration/parser/frame evidence on the board. The retained gate chains and related-clock recovery checks are concrete positive evidence, not proof that CSI frames now work.
