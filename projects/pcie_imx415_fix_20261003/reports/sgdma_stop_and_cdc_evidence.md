# Read-only SGDMA STOP and TD synchronizer evidence

No board operation, driver edit, TD launch, or frozen source edit was performed by this follow-up. Driver code is actively being repaired by the ISP review agent; the line references below identify the observed mechanisms, not a frozen final-driver manifest.

## SGDMA hardware STOP: confirmed gap

The local SGDMA implementation is protected. `fpga/uisrc/03_ip/sgdma/src_enc/sgdma_ip_all.enc.v:355` begins the protected region; line 383 declares AES128-CBC and line 19820 ends the region. The interface and enclosing wrapper are visible, but the engine's RUN/STOP, BUSY, final writeback, and PCIe request-retirement state machines are not. `fpga/uisrc/03_ip/sgdma/sgdma_subsys.v:831` connects the PH1 SGDMA reset only to `!user_reset`; there is no visible software-accessible per-engine reset/abort acknowledgment on that connection.

`fpga/deploy/sgdma_drv/anlogic_pci_lib.h:122` defines RUN/STOP as control bit 0, and line 135 defines BUSY as status bit 0. These definitions specify bit positions, not a proof that BUSY-zero includes all coherent completion-result writes and already-posted PCIe data transactions. The observed `sgdma_engine_stop` clears RUN through a control write and then reads status as a posted-write flush. At the time of review, `anlogic_pci_lib.c:1382-1384` already explicitly distinguishes this flush from a hardware BUSY-clear proof. Earlier timeout cleanup removed the transfer from the software list before immediately recycling its request/mapping; that sequence required repair regardless of whether the hardware usually becomes idle promptly.

The supplied ten-page `米联客2026版异构AFC03教程-PCIE篇.pdf` explains configuration, capture, inference, and autostart. It does not document STOP/reset/writeback ordering. The local PH1A PCIe hard-IP guide likewise does not establish the separately packaged SGDMA engine's drain protocol.

A primary-source web search found Anlogic's [official SGDMA overview, published 2023-05-06](https://www.anlogic.com/news/company-news/83.html). It explains normal C2H completion: data transmission precedes the completion interrupt, and the driver compares the completed-descriptor count before returning control. It supplies no RUN-zero abort rule, BUSY-zero final-writeback guarantee, reset acknowledgment, or maximum drain time. Searches restricted to Anlogic/MiLianKe plus exact SGDMA/BUSY/RUN/STOP terms found no relevant detailed primary-source guarantee. Other vendors' similarly named or register-compatible DMA manuals were intentionally not used as this core's specification.

Root observed both engine BUSY bits clear after STOP in the current test. This is useful execution evidence; it is not a specification for every outstanding transaction, link-error, starvation, or timeout case. Waiting for hardware BUSY-zero while retaining all DMA mappings/descriptors and preventing a new engine owner is the minimum defensible improvement. A fixed delay or software `running=0` alone is insufficient. If BUSY does not clear, warn and retain ownership/memory rather than freeing a DMA target that hardware may still use. A confirmed final-writeback/PCIe transaction drain guarantee remains an explicit vendor-documentation gap; no full proof is claimed here.

## TD 6.2.2 ASYNC_REG audit

Primary local manual references:

- `TD/doc/SWUG/SWUG105_TCL_Command_User_Guide.pdf`, PDF p48 (printed p41): `get_cells -filter {ASYNC_REG == true}` enumerates attributed cells. PDF pp58-59 (printed pp51-52) specify `get_property` and `report_property`.
- SWUG105 PDF pp101-102 (printed pp94-95): `report_mtbf` only analyzes synchronizer chains with `async_reg=true`. It requires constrained source/sink clocks, no chain timing violation, and nonzero switching activity to compute a defined value. TD 6.2.2 defaults the relevant processing off: enable `set_param rtl directive:async_reg on` and `set_param place async_reg on` and rebuild. PH1A is supported.
- `TD/doc/SWUG/SWUG106_HDL_Coding_Synthesis_User_Guide.pdf`, PDF pp44-45 (printed pp37-38): RTL ASYNC_REG acts as DONT_TOUCH in synthesis and is transmitted into the physical flow; attributed chain registers should be placed close. Adding only Tcl/ADC/SDC attributes does not guarantee that the original object survived earlier optimization.

The supplied `tools/cdc_attribute_audit.tcl` is a read-only helper. Root may source it in a fresh flow and invoke `cdc_attribute_audit $phase $task_out` after gate synthesis, after loading physical parameters, after the second `insert_debugger`, after placement, and after routing. It emits the actual cell count, names, and values into a new phase file and prints one cell's full properties to the build transcript. It does not add synchronizer properties or false paths, alter the flow, or launch a build.

These phase snapshots distinguish parameter overwrite from netlist-property loss and show the exact stage where a previously present attribute disappears. A zero count is explicitly unresolved. A nonzero count alone proves neither chain topology nor CDC safety; pair it with an intended-chain inventory, CDC source/sink clocks, routed synchronizer timing, MTBF report content, and the existing handshake/Gray-code design review. Re-marking a final imported netlist cannot retroactively prove that synthesis preserved the intended chains.
