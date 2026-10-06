# Driver07: probe/init error rollback

Only `fpga/deploy/sgdma_drv/anlogic_pci_lib.c` changed relative to the exact frozen driver06 source. `anlogic_thread.c` and `anlogic_pci_lib.h` retain their driver06 hashes. No board access, driver upload/load, kernel build, or TD invocation was performed here. The production source is ready for root's RK kernel build and controlled regression; hardware acceptance is pending.

## Original defect and minimal fix

The previous `probe_engines` treated both an absent next hardware channel and a real allocation/register-setup error as the end of that direction. It shrank the advertised maxima and returned zero. A failed partially initialized engine, and its IRQ-mask/count bookkeeping, could be outside the `remove_engines` loops. The device could appear successfully bound after ENOMEM or setup failure. These were original error-path defects; successful one-H2C/one-C2H probing does not exercise them.

- `probe_for_engine` now returns `-ENODEV` only for the hardware identifier/channel mismatch (`anlogic_pci_lib.c:4477`). An absent next channel still ends that direction normally. Real engine initialization failures retain their negative errno.
- `engine_init` publishes `MAGIC_ENGINE` only after allocations and register initialization succeed (`4407`). Both earlier failures use one rollback label (`4414`). No partial engine is presented as ready to clients or normal teardown.
- `engine_init_rollback` clears the direction's IRQ mask bit and calls the existing driver06 teardown (`4327`). All needed locks, lists, waitqueues and work initialization precede the failing allocations. Allocation failure already releases only allocations never published to hardware and sets their pointers NULL; the subsequent common teardown does not double free them.
- A programmed WB/descriptors target is freed only after the same STOP/drain path, polling-worker lease join and deferred-work cancellation used by driver06. The helper runs in process context without a spinlock held. Teardown preserves the existing lock order; it releases the engine lock before detaching the poll worker, performs blocking waits without the engine/work-list spinlocks, then clears the engine and decrements `engines_num`.
- `probe_engines` keeps successful H2C/C2H counts separately (`4590`). A genuine error first cleans the failed partial engine in `engine_init`, then cleans successful C2H engines in descending order and successful H2C engines in descending order (`4628`). It clears both maxima and returns the original negative errno. No engine in either direction is stranded by a prematurely shortened maximum. A device with no implemented engine returns `-ENODEV`.
- Probe disables channel/user interrupts and flushes those writes before probing (`4705`). IRQ/MSI allocation happens only after probe succeeds (`4720`). Thus this rollback has no live device IRQ handler to join; the existing outer device-open failure labels subsequently unmap BARs, release regions/device and stop the final global poll threads (`4754`). The external `anlogic_device_open` API still uses its existing NULL-on-failure contract; it is not an errno-returning API.

The harmless unsigned channel comparison cast also removes the strict host compiler warning. Normal successful probe, synchronous submit, generation/cancellation, worker-lifetime and physical-stop behavior were not changed. No extra lib.h initialization flag is necessary because existing initialized locks/work/null resource pointers and delayed magic publication are sufficient for this serialized error path.

## Actual local verification

`python tools/check_probe_rollback.py` extracts and compiles the five actual production functions (`engine_init_rollback`, `engine_init`, `probe_for_engine`, `engine_destroy`, `probe_engines`) with `C:/MinGW/bin/gcc.exe -std=gnu11 -Wall -Wextra -Werror -O2` and deterministic kernel/MMIO/allocation/thread mocks. It actually runs the resulting executable:

```
PASS PROBE_ROLLBACK_C cases=416 injected_failures=384
```

The cases cover interrupt/poll modes, 0–3 channels in each direction, no-engine rejection, normal absent-next-channel completion, and failure at every reachable descriptor/WB/result allocation and register-setup stage. Assertions check exact errno, NULL/magic/resource balance, IRQ-mask and engine-count balance, worker join and stop-before-programmed-memory-free, and failed-partial-then-reverse-success rollback order. The first failed compile log is retained as `evidence/driver_probe07_hostcheck/compile_first_failed.log`; it exposed a mock macro omission and the pre-existing signed comparison warning, both corrected before the successful run.

`python tools/check_poll_cancel.py` also passed after the change: 20 poll interleavings, 10 lifetime interleavings, 66 stop states and 24 source guards. Its negative controls still detect stale service and cancelled timeout.

These are host C/static model results, not a kernel module build, lockdep run or hardware proof. Mocks assume STOP/drain succeeds; the encrypted SGDMA core's final posted-WB semantics remain the previously documented vendor-information gap. Real RK compilation and controlled capture, STREAMOFF/restart, bidirectional image round trips and unload/reload after clients close remain root's acceptance steps. Concurrent active-client hot unbind was deliberately outside this patch and must not be advertised as supported.

## Frozen evidence

`evidence/driver_probe_before/anlogic_pci_lib.c` reconstructs the exact driver06 file from the saved driver05 baseline and recorded driver06 diff and verifies the original SHA-256 before saving it. `evidence/driver_probe_error07.patch` contains the exact 06→07 diff. `evidence/driver_probe_error07_manifest.json` records source hashes, diff hash, compiler, executable result and unrun acceptance steps. `evidence/driver_probe07_hostcheck/result.json`, `compile.log` and `selfcheck.log` contain the successful run evidence.
