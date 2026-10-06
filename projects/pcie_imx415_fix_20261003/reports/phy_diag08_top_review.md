# CSI diagnostic08 top independent review

Date: 2026-10-05. Scope: read-only source review of issue1 (CSI receives no complete frame). No source edit, TD launch, board action, or bidirectional-image test was performed for this review. The two inherited AXI issues below are registered as **issue13**, deferred while issue1 is investigated.

## Result for the new diagnostic interface

No blocking error was found in the new register map or candidate-to-candidate port connections. This is permission to proceed with combined08 compilation and physical diagnosis, not proof that the PHY receives valid frames.

Reviewed top: `tools/phy_diag08/imx415_pcie_top.v`, SHA256 `fe69b14bcfd4aadd6b4debfa1d5e6d9cb6978ceb9278bc2c4142a66550339df7`. Generator: `tools/prepare_phy08_top.py`, SHA256 `cb2d5ce5d595b4197799cc76497cbd483044207ea59514e69effc2b089297356`. The generator checks frozen07 input SHA and unique replacement anchors, writes the candidate, and does not modify main07 top.

- Top lines909–912 require upper16 read-address bits zero and select only 0x0040..0x011C. Line921 uses a 16-bit case. New addresses0x0100..0x011C therefore do not alias0x0000..0x001C. Vendor IRQ address0x0128 is outside the intercept range and passes to the unchanged SGDMA application.
- E0 is a seven-bit user-clock shadow: bit6 override-enable, bits5:0 requested tap; reset0 selects automatic mode (lines874/891/995). Top cam connections557–563 match `cam_video_source.v` ports64–67. Snapshot outputs are224bits including source-cycle count; receiver diagnostic payloads are192bits.
- `cam_video_source.v` lines197–204 use the actual unchanged held-bus snapshot, byte-clock source to user-clock destination. Receiver lines113–115 transfer the seven-bit command coherently in the opposite direction. Receiver PHY connections190–193 match `tools/csi_reset8/csi_rx_phy.v` ports30–31/48–49; raw bytes are32bits at four lanes, and sampler reset is synchronized through three byte-clock FFs before joining the diagnostic payload (receiver102–107).
- The command-period timer belongs to destination byte clock:125000 cycles is about1.122ms at111.375MHz. Diagnostic snapshot periods are12.5M user clocks, about100ms at125MHz. A command cannot apply while the byte clock is stopped. E0 reading proves only the written shadow; applied control must be read from a completed diagnostic snapshot.

| BAR address | Source / meaning | Snapshot bookend |
|---|---|---|
| E0 | user shadow ctrl7 | no snapshot |
| E4 | bank0 `{sequence,busy}` status | E4 |
| E8/EC/F0/F4 | lane0/1/2/3 aligned-valid cycle counts | E4 |
| F8 | raw unaligned sampled byte word | E4 |
| FC | flags: sticky7:0, applied ctrl7 at14:8, sampler-reset-n at15, delay23:16, mipi31:24 | E4 |
| 100 | bank1 `{sequence,busy}` status | 100 |
| 104/108/10C | FS count / prior observed payload-line count / current count | 100 |
| 110/114/118 | packet-error pulses / aligned word-valid cycles / payload-valid beats | 100 |
| 11C | bank0 ctrl8 = sampler-reset-n bit7 + applied ctrl7 bits6:0 | **E4**, not100 |

For each bank, read its status before and after the associated data and reject if `status>>1` changes. Reject sequence0 for an uninitialized snapshot and require sequence advancement when proving a clock remains active. Do not assume bank0 and bank1 are from one common sampling instant. Busy is request/ack status, not a CRC/PHY-valid indication. New payload-line counters count observed boundaries even for a later CRC-bad packet; they must not be reported as accepted or CRC-good image rows. Clock-delta outputs are intentionally unconnected at top; this review does not extend the BAR map.

## Issue13: inherited AXI read/write weaknesses, deferred

These conditions existed in the prior top/interface and were not introduced by the diagnostic address extension. Parent explicitly deferred their repair. Current CPU diagnostics use aligned32-bit, full-strobe accesses with immediate RREADY; neither this review nor held-snapshot bookends prove arbitrary AXI transaction correctness.

### Read response may change under backpressure

Candidate top lines905–912 assign `vid_rd_sel_d1` from the current ARVALID/address every cycle, not from a retained outstanding read. Lines920–921 similarly update `vid_reg_rdata_d1` from the live ARADDR every cycle, and line1015 directly selects this result or `app_axil_rdata`.

Concrete trigger: accept an intercepted read with ARVALID=1 and ARREADY=1, then deassert ARVALID while RREADY=0. The unchanged vendor `axil_anal.v` lines130–135 keeps RVALID asserted until RREADY, but after the next user edge the top's select becomes0 and RDATA changes to the application value during the outstanding response. Changing ARADDR while the response is stalled can also change the selected register data. AXI requires RDATA to remain stable while RVALID=1/RREADY=0. The vendor itself has ARREADY tied1 (line85) and only low8 read-address retention (lines193–197); a future repair must consider outstanding-response acceptance, not just add an address FF.

No RREADY-stall simulation or board trigger was run here. This is a source-level counterexample, not evidence that the current immediate-ready CPU reads have failed.

### Upper-address alias and ignored byte strobe on top writes

Candidate top `wr_hit` (lines861–862) checks AWVALID/WVALID and only `AWADDR[15:8]==0`. The write case uses low8bits (line884), and E0 takes live WDATA[6:0] (line891). There is no upper16 write-address check and no WSTRB[0] check.

Concrete trigger1: a rising `wr_hit` at AWADDR=0x000100E0 writes the same PHY shadow as0x000000E0 because upper16bits are ignored. By contrast, read0x000100E0 is correctly excluded by the new read guard. AWADDR=0x00000128 does not hit this top write path because byte1 is1; it is not an E0 alias.

Concrete trigger2: at AWADDR=E0, WSTRB[0]=0 (including a zero-strobe write or a write enabling only another byte), the top still replaces ctrl7 using WDATA[6:0]. Disabled bytes should not modify this low-byte register. Existing A4/D8/control/mode/gain writes share this issue. Vendor `axil_anal.v` lines158–161 applies strobes to its own internal write-data path, but that path does not guard these top-level raw-WDATA assignments.

No alias/strobe board access was issued. Future issue13 repair should add precise high-address qualification, byte-write enables and a handshake-based retained response path with meaningful stall tests. Main07 and all08 candidate source files remain unchanged by this review.
