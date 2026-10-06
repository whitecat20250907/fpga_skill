# Issue1 prerequisite: BAR0 read-address normalization review

2026-10-05. Independent read-only review. No source change, TD/simulator invocation, or board access. This review evaluates the proposed narrow read qualifier, not deferred general AXI repair.

## Conclusion and exact contract

The proposed `[19:16] == 4'h0` qualifier is correct **for the currently verified 32-bit, 1 MiB BAR0, aligned to 1 MiB**, with AXI-Lite requests already selected for BAR0 by the upstream bridge. Ignore only BAR base/prefix bits `[31:20]`, preserve all 20 offset bits, then require the offset to lie in the existing `0x0040..0x011C` low register window.

For a legal host access `A = BAR0_base + O`, `0 <= O < 2^20`, BAR0_base has zero low 20 bits, so `A[19:0] = O`. This holds whether the downstream engine presents the original 32-bit physical address, the normalized 20-bit offset, or a 26-bit masked physical address with residual base bits `[25:20]`. The proposed qualifier accepts register offsets in each representation without permitting in-BAR 64 KiB/512 KiB register aliases.

The encrypted SGDMA engine prevents text inspection of its precise normalization algorithm. The algebra establishes compatibility with these possible address representations; it does **not** prove which representation the currently running engine emits, or uniquely establish the current readback failure's cause. Parent-owned accepted-AR observation or the narrowly corrected immutable-version readback is still the hardware discrimination.

## Evidence of the current aperture and path

Parent supplied actual RK PCI resources:

| Resource | Inclusive physical interval | Size |
|---|---|---:|
| BAR0/user | `0x21200000..0x212FFFFF` | 1 MiB |
| BAR1/DMA config | `0x21300000..0x2130FFFF` | 64 KiB |

Local IP source independently agrees:

- `fpga/al_ip/PH1_LOGIC_PCIE.ipc:124-130`: enabled Memory BAR0, 32-bit, size 2^0 M Bytes, mask `FFF00000`.
- `fpga/al_ip/pcie_brg_pcie_core/pcie_brg_pcie_core.v:860-865`: BAR0 32-bit and `32'hFFF00000`, BAR1 `32'hFFFF0000`.
- `fpga/uisrc/03_ip/sgdma/src_enc/sgdma_ip_all.enc.v:58-59`: `DMA_BAR=1`, `AXI4LITE_BAR=0`; `sgdma_subsys.v` does not override those two defaults. The bridge's actual normalizing body is encrypted.
- `fpga/deploy/pcie_setup.sh:36-41` maps the actual endpoint `resource0` at offset zero. `tools/read_csi_stats.py:13` and `tools/bar_roundtrip.c:13` also mmap user BAR offset zero. V4L2 obtains the user BAR base through `anlogic_get_user_bar`, then accesses base+register offset (`milianke_v4l2_zerocopy.c:783,791,799-801`).

No fixed RK physical BAR base should be encoded in FPGA logic. A future change in BAR0 size, selected user BAR, separate subwindow base, or interface address contract requires a new review and tests rather than copying this 20-bit contract blindly.

## Address examples (pure combinational evaluation, not board transactions)

All hits also require ARVALID. The low 16-bit full register case remains unchanged.

| Presented ARADDR | Interpretation | Old `[31:16]==0` | Proposed `[19:16]==0` + range |
|---|---|---|---|
| `0x2120005C` | physical BAR0 version | miss | hit |
| `0x0000005C` | normalized 20-bit version | hit | hit |
| `0x0120005C` | physical version masked to 26 bits | miss | hit |
| `0x21200100` | physical diagnostic register 0x100 | miss | hit |
| `0x00000100` | normalized diagnostic register | hit | hit |
| `0x2121005C` | BAR0 offset 0x1005C | miss | miss |
| `0x0001005C` | normalized offset 0x1005C | miss | miss |
| `0x2128005C` | BAR0 offset 0x8005C | miss | miss |
| `0x21200128` | vendor IRQ offset 0x128 | miss | miss |
| `0x00000128` | normalized IRQ offset | miss | miss |

Thus 0x100..0x11C no longer alias low-byte addresses, and 0x128 remains outside the video intercept. Within a legal 1 MiB BAR0 access, every offset above 64 KiB is rejected by the proposed high-offset check.

## CQ aperture mismatch remains separate

`pcie_rx_trgt2cq.v:347-348` explicitly says BAR size autodetection is unsupported and hardcodes `bar_aperture = 5'd26` (64 MiB). Lines 436-438 and 523-525 put that metadata into CQ; lines 449-452 and 510-513 preserve the original 64-bit target address. This 26-bit metadata is inconsistent with both the real 20-bit BAR0 and 16-bit BAR1 apertures.

If the encrypted engine masks by 26 bits, `0x2120005C` becomes `0x0120005C`; the proposed top qualifier still correctly recovers the register offset through its low 20 bits. This is a compatibility fix at the BAR0 video-read decoder, not a repair of the CQ adapter. It does not establish normalization, completion formation, config routing or byte-enable correctness for every BAR/interface. Do not simultaneously alter the CQ metadata based on guessed encrypted-core semantics during this issue1 prerequisite repair.

## Explicit scope limits

1. **Writes retain aliases and ignored byte strobes.** Top `imx415_pcie_top.v:861-862` checks only AWADDR[15:8] with raw AWVALID/WVALID, and the cases at 884 onward use AWADDR[7:0] and live WDATA without WSTRB. The narrow read-guard candidate does not repair those paths or prove arbitrary separate AW/W and back-to-back handshakes.
2. **Read-response stall stability remains unresolved.** Top lines 905-912 and 920-921 track live ARVALID/ARADDR. Vendor `axil_anal.v:130-135` retains RVALID until RREADY; `ARREADY` is always 1 at line 85. A stalled response can therefore outlive the select/address that produced it. Normal CPU immediate-ready MMIO readback is not a proof of arbitrary AXI read backpressure.
3. **CHAR_USER read/write methods have a different legacy subwindow.** `anlogic_pci_cdev.c:317,324` starts with base zero then sets CHAR_USER base to `SGDMA_USER_BAR_BASE_OFFSET=0x80000` (`anlogic_pci_lib.h:83`). `cdev_ctrl.c:64,100` adds that base for pread/pwrite; its mmap path at 324-326 maps PCI resource base+page offset without adding it. The current diagnostic mmap/V4L2 direct path is BAR0+0. The proposed first-register-page guard intentionally does not make offset 0x8005C a version-register alias, so a successful mmap check cannot be described as testing all CHAR_USER pread/pwrite methods. General alias/API consistency is deferred.
4. **Camera state cannot be inferred from the old all-zero video reads.** The setup writes gain 0x98=100 before printing it; application RAM in `axil_anal.v:209-216` mirrors writes using low address bits. Gain100 alone can be the application mirror. The immutable version, fixed pixel format, dimensions and diagnostic registers must read correctly first.

Required parent-owned acceptance for this narrow prerequisite is the expected immutable build version at 0x5C and the correct static register values through the actual BAR0 mmap path, with 0x100..0x11C distinct and 0x128 excluded. Raw ARADDR observation would confirm the concrete bridge representation. This review does not certify a new bit, corrected CSI acquisition, general BAR/AXI health, write strobes, stall behavior, or CQ aperture repair.
