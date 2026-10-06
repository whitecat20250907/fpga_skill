# SGDMA poll cancellation and stop-retention review (driver06 candidate)

Status: source frozen for the parent to compile and test on RK. This review did
not compile any kernel module or access the board. Software interleaving models
are evidence of the concurrency design, not proof of hardware DMA completion.

## Observed fault and concrete source defects

`evidence/rk_serial.log` contains a normal 120-frame capture followed by
STREAMOFF / interrupted sync DMA (`wait=-512`, state SUBMITTED, pre-STOP BUSY=1).
Driver05 returned immediately after abort/STOP and ten seconds later its poll
worker printed `Polling timeout occurred` and `not get comp desc at this poll work`.
The parent separately read both idle hardware channels after capture: H2C0
control/status=0/0, C2H0 control/status=0x04f83e18/0 (RUN=0, BUSY=0).

The old worker dereferenced `engine->transfer_list.next` without `engine->lock`;
`list_entry` on an empty-list sentinel is not NULL. Abort could delete/free the
embedded request concurrently with the threshold read. The WB monitor itself
kept an engine pointer and a scalar threshold, not the transfer pointer, but
ignored abort/running/shutdown/restart while waiting. Thus a cancelled request
could log a late timeout, and a rapid new run could be serviced by old poll work.
The work-list iterator ran unlocked; concurrent detach/free could invalidate its
engine or next pointer. `remove_work` detached without joining in-flight work,
while `engine_destroy` freed engine WB before global threads were stopped.

## Changes, only the three authorized driver files

- `anlogic_thread.c`: snapshot head completion threshold and generation while
  holding the engine lock; only those scalars leave the lock. Select/rotate a
  work item while holding the thread-list lock and obtain an engine lifetime
  lease under the engine lock. Do not retain an iterator's next pointer across
  processing. Drop the final lease under lock and never access engine afterwards.
- `anlogic_pci_lib.h/.c`: stop, abort, start and an empty-to-nonempty head each
  change a 64-bit generation. Validate it under lock before every WB read/clear
  and again before completion service. Cancellation returns ECANCELED without
  a spurious timeout/error log; a still-current running request retains its
  genuine timeout report. Existing two-argument cyclic API remains compatible.
- Removal first marks the engine removing and invalidates its generation,
  detaches the list node, waits for leases to reach zero, then acquires/releases
  the engine lock as a final lifetime barrier. IRQs are torn down before engine
  removal; already queued deferred IRQ work is joined using cancel_work_sync.
  Failed thread creation also joins earlier live threads before freeing storage.
- Abort/error handling gates new queue/start using dma_quiescing. Both synchronous
  abnormal submit exits keep their request, SG mapping, externally owned buffer
  and descriptor mutex while checking the physical control RUN and status BUSY.
  They issue STOP even if the diagnostic status read failed. Only RUN=0/BUSY=0
  allows old WB clearing, reopening the gate and subsequent destroy/unmap.
  Engine teardown likewise confirms idle before freeing engine descriptors/WB.
  Reads and state changes use the engine lock; waits/sleeps occur outside it.
- Normal immediate idle uses MMIO reads and adds no fixed sleep. If STOP remains
  unconfirmed after one second, the driver visibly reports that DMA mappings are
  retained and continues waiting in process context, ignoring signals as a
  permission to release memory. This is fail-closed retention, not a successful
  reset or bounded recovery. A permanently stuck core requires diagnosis/reset.

## Hardware protocol boundary

Local `src_enc/sgdma_ip_all.enc.v` is AES-protected. The top has no independent
software channel-reset handshake. Available local PCIe IP manuals and the
10-page Milianke PCIe tutorial do not define RUN=0 -> BUSY=0 -> final posted WB
ordering. The official Anlogic overview describes only normal transfer/completion:
https://www.anlogic.com/news/company-news/83.html
Do not assume AMD XDMA semantics because the register/driver names look similar.
BUSY=0 is a real channel-idle observation; whether it includes all downstream
PCIe posted writeback draining is not documented here. No fixed-delay substitute
or invented reset register was added. This boundary requires vendor confirmation
if formal DMA-quiescence proof is needed. The board regression must still expose
late writes, mapping leaks, stale completions and restart failures.

The scope covers the deployed synchronous C2H/H2C and poll-worker paths. Existing
unused async callback/performance/debug APIs are not declared universally safe:
some of them call lock-required engine operations without a visible lock or
free cyclic/performance buffers under a spinlock. Those callers are outside
this focused synchronous board acceptance; do not enable them as reusable APIs
without a separate audit. Hot removal while MMIO is inaccessible also cannot be
called a verified recovery path; retention deliberately blocks unsafe freeing.

## Verification and required board acceptance

`tools/check_poll_cancel.py` passed 20 old-worker/restart interleavings, 10 engine
lifetime interleavings, 66 stop/retention states and 24 source guards. It covers
persistent BUSY, delayed clear, retained memory despite signal/deadline, WB clear
only after confirmed idle, new epoch WB preservation, empty-head guards and
service generation recheck. Negative controls detect the baseline stale-service
and cancelled-timeout races. Vendor preambles were preserved; the exact scoped
patch is `evidence/driver_poll_cancel06.patch`. Structural checks are not a C
compiler or lockdep.

Parent owns: actual RK kernel build; 20 STREAMON/STREAMOFF runs; wait >10 seconds
after normal stop with no residual worker timeout; raw SIGTERM interruption and
recovery; H2C/C2H complete RGB round trips; unload/reload after stop; 1000-frame
capture; repeated CMA/map-SG accounting before/after. A fail-closed retained-map
log must count as an unresolved hardware stop fault, not be hidden or accepted.
Do not claim any of these board checks passed from the model output.

## Frozen SHA-256

- `anlogic_pci_lib.c`: `bc937ca2d1e87405bff600da4d697d26bc8dbb404e28b3f5e62531cb5c725875`
- `anlogic_thread.c`: `a03a6da86c989a2297fbd76081c81e5d945f57542419105983fd6aa25d668801`
- `anlogic_pci_lib.h`: `31e98c5e55d30a8d53cca99e2cfc2695907bfa47154fa96463c237ca4923754d`
