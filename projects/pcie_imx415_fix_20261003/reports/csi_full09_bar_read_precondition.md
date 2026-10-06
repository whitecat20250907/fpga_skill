# Issue1 receive precondition: build09 video BAR reads return zero

2026-10-05. Read-only source investigation. No FPGA/driver edit, TD invocation, board action or alternate-link test. This report investigates the observed receive-diagnostic prerequisite, not all deferred issue13 AXI improvements.

## Actual observation supplied by root

Build09 SRAM download succeeded in18.42s; controlled RK rebind/setup returned0 and PCIe Gen2x1 is visible. Reads of version0x5C, camera status0x84 and width/height are0. Gain0x98 reads100. The diagnostic09 version guard correctly refused to continue; no image capture was accepted. These facts alone do not establish the running bit's version or CSI's state, because the read interception may have failed.

## Strongest source-supported explanation: new upper-address guard

`tools/prepare_phy08_top.py` lines34–41 replaced the old read selection:

```verilog
(m_axil_araddr[15:8] == 0) && low8 >= 8'h40 && low8 <= 8'hDC
```

with a16-bit-range selection that also newly requires:

```verilog
(m_axil_araddr[31:16] == 16'h0000) &&
(m_axil_araddr[15:0] >= 16'h0040) &&
(m_axil_araddr[15:0] <= 16'h011C)
```

The latter is frozen full09 top lines909–912. Its16-bit case at921 correctly prevents0x0100 aliasing low8 and excludes0x0128 IRQ, but **the extra upper16-zero check assumes the AXI address is already a pure BAR offset**. That address contract was not validated in the earlier independent map review. The existing write hit at861–862 still ignores upper16bits, creating an asymmetric read/write qualification.

Real PH1A bridge source `pcie_rx_trgt2cq.v` lines449–452 and510–513 carries the received64-bit target address's high32 and low `[31:2]` unchanged into CQ headers. Lines347–348 explicitly state BAR-size autodetection is unsupported and hardcode BAR aperture26bits. Its AXI-generation engine `src_enc/sgdma_ip_all.enc.v` is encrypted; this reviewer cannot establish from plaintext that it subtracts the actual BAR base or reduces the address to16bits. The native IP configuration `PH1_LOGIC_PCIE.ipc` lines124–130 configures BAR0 as1MiB, maskFFF00000 (20-bit offset), which is narrower than that26-bit CQ aperture.

If the AXI engine presents a physical address or a26-bit masked physical address with nonzero bits31:16, every video read fails the new guard. The top then selects the vendor application RAM/IRQ path. This explains constant/read-only video registers returning0 without requiring broken camera hardware. It is the leading regression candidate, **not yet a uniquely proven hardware root cause**; actual ARADDR/RREADY observation or a narrowly corrected candidate must discriminate it from response timing.

## Why gain100 is not evidence that video interception works

Actual setup script `fpga/deploy/pcie_setup.sh` line40 explicitly writes gain0x98=100 before line42's diagnostic print. The unchanged vendor `axil_anal.v` lines209–216 mirrors such writes into512×32 application RAM at low address bits10:2 and reads that RAM in one clock. Therefore gain100 can be only the write mirror when the video intercept is bypassed. Version, width, height and camera status are not written by this setup and can instead read RAM0.

This is a source-backed explanation for the precise observation, stronger than interpreting gain100 as proof of top register selection or interpreting version0 as proof that SRAM download failed.

## Read latency and deferred response stability

Under the expected same user-clock, immediate-ready single read, the unchanged application's ARREADY is1 (`axil_anal.v`85); its RVALID rises one edge after accepted AR (130–135). The top's registered select and registered register data also update at that edge. There is no newly added extra video read-data pipeline stage in08/09; the new functionality changes address qualification and case width.

However, the top continues to update select from live ARVALID/address and data from live ARADDR every cycle (905–912/920–921), while vendor RVALID may remain high until RREADY. If the bridge does backpressure, ARVALID can drop while the response is pending and the top mux at1015 can switch to application data. That is the inherited issue13 response-stability counterexample, not an accepted explanation for the current board unless the actual bridge transaction timing is observed. No arbitrary-stall simulation/hardware evidence was produced in this read-only investigation.

## Narrow candidate and required discrimination

Root owns changes and validation. A minimal compatibility candidate removes only the unsupported upper16-zero requirement, retains the low16 `0040..011C` comparison and16-bit case, and therefore still does not intercept0x0128. This restores the prior tolerance of address-prefix bits without concurrently repairing all deferred issue13 behavior. It intentionally retains broader high-offset aliases until the actual BAR-address contract is known.

If the current user interface is confirmed to be this1MiB BAR0, a stricter normalization candidate ignores only base bits31:20 and requires offset bits19:16=0 before the same low16 range. It must be derived from the verified BAR aperture, not a fixed guessed RK physical base. Different BAR mapping/aperture requires different normalization.

Useful root-owned discrimination is the actual resource0 base/length and, if available through the existing debugger, accepted ARADDR plus ARVALID/RVALID/RREADY at version0x5C. A correct immutable version and constant pixel-format/source-select reads after the narrow candidate would establish interception before any CSI capture claim. A RAM mirror alone cannot do so. The receive issue remains unresolved until this prerequisite and physical acquisition pass.
