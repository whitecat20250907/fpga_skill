# Independent read-only driver06 review

Reviewed the final three-file source against `reports/poll_cancel_review.md`. No source change, board access, kernel-module build, or TD operation was performed. The reviewed hashes match that report exactly:

- `anlogic_pci_lib.c`: `bc937ca2d1e87405bff600da4d697d26bc8dbb404e28b3f5e62531cb5c725875`
- `anlogic_thread.c`: `a03a6da86c989a2297fbd76081c81e5d945f57542419105983fd6aa25d668801`
- `anlogic_pci_lib.h`: `31e98c5e55d30a8d53cca99e2cfc2695907bfa47154fa96463c237ca4923754d`

## Result and acceptance scope

No newly introduced locking or cancellation defect was found that blocks root's controlled loading and testing of the deployed synchronous C2H/H2C paths. This is a source-review result, not kernel compilation, lockdep, hardware-drain proof, or a claim that the regression has passed. Root must still run capture/STREAMOFF, delayed residual-log checks, interrupted raw transfers and recovery, complete image round trips, and normal unload/reload with no active client.

The permanent-BUSY path deliberately retains mappings and can block STREAMOFF or removal indefinitely. That behavior prevents an unsafe DMA-target release; it is an unresolved hardware-stop fault, not successful bounded recovery. The vendor-documentation gap over whether BUSY-zero includes the last downstream posted writeback remains separate and cannot be resolved by CPU memory barriers alone.

## Lock order and lifetime

- Synchronous submissions acquire `desc_lock` and then briefly `engine->lock` (`anlogic_pci_lib.c:3032`, 3101); their stop-wait retains the descriptor mutex but sleeps only after releasing the engine spinlock (1396-1422). No deployed completion-worker path acquires `desc_lock`, so the submitter waiting for completion does not prevent the worker from completing or cancelling it.
- The poll thread selects an engine under its work-list lock and acquires the engine lock only inside that region (`anlogic_thread.c:125-128`, 81-90). It releases the work-list lock before calling the completion function. No engine-lock-to-work-list-lock nesting was found in the reviewed deployed paths.
- Removal sets `poll_removing`, invalidates generation, and snapshots/nulls `cmplthp` under the engine lock; it releases that lock before taking the work-list lock to detach the node (230-241). It waits for worker leases without either spinlock and then crosses the engine lock as a final barrier (243-247).
- A selected worker owns a scalar lifetime lease; it copies only the threshold and generation while the transfer-head lock is held (58-70). Its final engine access is the lease decrement/wakeup under the engine lock (136-140). The final removal barrier waits until that critical section is entirely finished before engine memory can be cleared.
- Normal device close tears down IRQs before `remove_engines` (`anlogic_pci_lib.c:4748-4753`). Engine teardown invalidates new polling, detaches and joins poll leases, joins deferred IRQ work through `cancel_work_sync`, confirms physical idle, and only then frees descriptors/results/WB memory (4494-4525). Global poll threads are stopped later when the final device is removed (135-146). No blocking wait occurs under the engine or work-list spinlock in these paths.

## Cancellation, physical stop and WB generation

The two synchronous wait/abort blocks always issue STOP even when their diagnostic status read fails (2899-2910 and 3143-3154). Timeout, signal and FAILED exits reach `engine_wait_stopped` before descriptor destruction and SG unmapping (2921-2928 and 3165-3177). Request memory, descriptor ownership and externally supplied vb2/user buffers remain live during that wait. A deadline or signal is not used as permission to free them.

The wait checks real RUN/BUSY MMIO under the engine lock; it clears the retained WB and `dma_quiescing` only after RUN-zero/BUSY-zero (1397-1413). The synchronous caller still owns `desc_lock` while that gate reopens, so another deployed synchronous submission cannot rewrite its descriptors before the previous caller destroys them and releases the mutex. `poll_removing` independently blocks starts during removal.

Polling validates engine running/removal and generation while holding the engine lock before every WB read/clear (2219-2231). It copies no transfer pointer outside the lock. Completion service reacquires the same lock and validates the generation again (2296-2311); cancellation or a new start cannot cause the old scalar threshold to service the new transfer head. Cancellation returns ECANCELED without the old ten-second timeout log. The worker lease protects the WB allocation while these checks execute.

The CPU spinlock does not serialize PCIe device writes; the existing simultaneous device-WB-update protocol remains a hardware/software interface assumption. The patch correctly prevents CPU work from clearing a new software generation, while the documented hardware drain boundary remains unresolved. The deployed default descriptor-completion and C2H register-fallback paths still require the actual board regression.

## Separate original defects and exclusions

1. **Probe/allocation failure is swallowed and may leak a partial engine.** `engine_init` returns an allocation or register-setup failure at 4386-4392. `probe_engines` shrinks the advertised channel maximum to the count of successful engines (4583/4590) and then unconditionally returns zero (4592). The partially initialized failed engine can therefore be omitted by `remove_engines`, whose loops only cover those successful maxima (4544/4555). This is an original error-path defect, not introduced by driver06; successful present-board one-H2C/one-C2H probing does not trigger it. A separate patch should distinguish identifier-mismatch/end-of-channel from real initialization failure, retain/clean the partial engine, and propagate real ENOMEM/setup errors before declaring all error recovery complete.
2. **Hot unbind with a concurrent submitting client is outside this review's normal unload acceptance.** The submit path checks `engine->cmplthp` and then the wakeup macro dereferences that expression again (2854-2855 and 3088-3089), while removal can null it (thread.c:234). A concurrent hot removal can race these reads; broader active-client lifetime is also not joined by `engine_destroy` through `desc_lock`. Ordinary module removal is tested only after clients close and the V4L2 module releases its dependency. Do not advertise active hot-unplug as supported without a separate client-lifetime design.
3. The report's exclusions for unused async, cyclic/performance/debug APIs are justified. They retain old lock-required call sites and buffer-lifetime assumptions. A correct focused synchronous path does not validate every exported internal API.

No driver patch was applied as part of this independent review.
