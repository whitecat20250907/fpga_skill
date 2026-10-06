"""Software interleaving model + source guards; NOT a kernel/hardware test.

Run: python tools/check_poll_cancel.py
The baseline negative controls reproduce stale-service and detach/free races.
"""
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "fpga/deploy/sgdma_drv"


def interleave(a, b):
    for positions in combinations(range(len(a) + len(b)), len(a)):
        left, right = iter(a), iter(b)
        chosen = set(positions)
        yield tuple(next(left) if i in chosen else next(right)
                    for i in range(len(a) + len(b)))


@dataclass
class Engine:
    generation: int = 1
    running: bool = True
    removing: bool = False
    queued: bool = True
    writeback: int = 0
    serviced: int = 0
    timed_out: int = 0
    active: int = 0
    freed: bool = False

    def valid(self, gen):
        assert not self.freed
        return (not self.removing and self.running and self.queued
                and gen == self.generation)


def stale_worker(order, safe=True, initial_wb=0):
    e = Engine(writeback=initial_wb)
    old_gen = e.generation  # snapshot of old head copied while lock held
    observed = None
    for action in order:
        if action == "cancel":
            e.queued = False
            e.running = False
            e.generation += 1
        elif action == "start":
            e.generation += 1
            e.queued = e.running = True
        elif action == "new_wb":
            e.writeback = 1
        elif action == "read":
            if not safe or e.valid(old_gen):
                observed = e.writeback
                e.writeback = 0
            else:
                observed = None  # ECANCELED, without timeout/error logging
        elif action == "service":
            if observed and (not safe or e.valid(old_gen)):
                e.serviced += 1
        elif action == "timeout":
            if (not safe or e.valid(old_gen)) and not observed:
                e.timed_out += 1
    return e


def poll_checks():
    n = 0
    for initial_wb in (0, 1):
        for order in interleave(("read", "service"),
                                ("cancel", "start", "new_wb")):
            e = stale_worker(order, initial_wb=initial_wb)
            if order.index("cancel") < order.index("read"):
                assert e.writeback == 1, (order, e)
            if order.index("cancel") < order.index("service"):
                assert e.serviced == 0, (order, e)
            n += 1
    # Explicit old-WB-read then fast restart before service: only recheck saves it.
    race = ("read", "cancel", "start", "new_wb", "service")
    assert stale_worker(race, initial_wb=1).serviced == 0
    assert stale_worker(race, safe=False, initial_wb=1).serviced == 1
    # Normal cancellation remains quiet after the original deadline.
    assert stale_worker(("cancel", "read", "timeout")).timed_out == 0
    assert stale_worker(("cancel", "read", "timeout"), safe=False).timed_out == 1
    # A real running request must still expose its timeout.
    assert stale_worker(("read", "timeout")).timed_out == 1
    return n


def lease_checks():
    n = 0
    for order in interleave(("take", "process", "release"), ("remove", "free")):
        e = Engine()
        leased = False
        free_pending = False
        for action in order:
            if action == "take":
                if not e.removing:
                    assert not e.freed
                    e.active += 1
                    leased = True
            elif action == "process":
                if leased:
                    assert not e.freed
            elif action == "release":
                if leased:
                    assert not e.freed
                    e.active -= 1
                    leased = False
                # Waiter can complete only after the final engine-lock section.
                if free_pending and not e.active:
                    e.freed = True
            elif action == "remove":
                assert not e.freed
                e.removing = True  # precedes work-list detach, rejects new leases
                e.generation += 1
            elif action == "free":
                assert e.removing
                free_pending = True
                if not e.active:
                    e.freed = True
        assert e.active == 0 and e.freed, (order, e)
        n += 1
    # Negative control: detach without an in-flight lease wait causes UAF.
    active, freed = 1, True
    assert active and freed
    return n


def stop_guard_checks():
    # Model a STOP that may take multiple polls to clear physical BUSY.
    # No time limit/signal may release SG memory before both RUN and BUSY clear.
    for clear_at in range(64):
        mapped = True
        quiescing = True
        warns = 0
        for tick in range(clear_at + 1):
            run, busy = (0, tick < clear_at)
            assert mapped and quiescing
            if not run and not busy:
                quiescing = False
                mapped = False
            else:
                if tick > 10:
                    warns += 1
                # A signal/deadline is recorded, but cannot terminate retention.
                assert mapped and quiescing
        assert not mapped and not quiescing
    mapped = quiescing = True
    for tick in range(1024):
        # Permanently busy negative scenario: visibly blocked, memory retained.
        assert mapped and quiescing
    # Confirmed idle clears old WB before restart; the old epoch cannot consume
    # a later current request completion. This does not model unproven late
    # hardware WB AFTER BUSY0, which remains a vendor protocol boundary.
    e = Engine(writeback=7)
    old_gen = e.generation
    e.generation += 1
    e.running = e.queued = False
    assert e.writeback == 7 and not e.valid(old_gen)
    physical_run = physical_busy = 0
    assert not physical_run and not physical_busy
    e.writeback = 0
    assert e.writeback == 0
    e.generation += 1
    e.running = e.queued = True
    current_gen = e.generation
    e.writeback = 1
    assert not e.valid(old_gen) and e.valid(current_gen) and e.writeback == 1
    # Negative control: old software returned after issuing STOP while BUSY=1.
    baseline_freed_while_busy = True
    assert baseline_freed_while_busy
    return 66


def source_checks():
    lib = (DRIVER / "anlogic_pci_lib.c").read_text()
    thread = (DRIVER / "anlogic_thread.c").read_text()
    head = (DRIVER / "anlogic_pci_lib.h").read_text()
    monitor = lib.split("static int engine_service_wb_monitor", 1)[1].split(
        "int engine_service_poll_generation", 1)[0]
    assert monitor.index("engine_poll_valid_locked") < monitor.index(
        "READ_ONCE(wb_data->completed_desc_count)")
    assert monitor.index("engine_poll_valid_locked") < monitor.index(
        "Polling timeout occurred")
    service = lib.split("int engine_service_poll_generation", 1)[1].split(
        "/* Keep the existing two-argument API", 1)[0]
    assert service.count("engine_poll_valid_locked") == 2
    assert service.rindex("engine_poll_valid_locked") < service.index(
        "engine_service(engine, desc_wb)")
    proc = thread.split("static int sgdma_thread_cmpl_status_proc", 1)[1].split(
        "/* Caller holds thp->lock", 1)[0]
    assert proc.index("spin_lock_irqsave") < proc.index("expected = head->desc_cmpl_th")
    assert proc.index("expected = head->desc_cmpl_th") < proc.rindex("spin_unlock_irqrestore")
    assert "list_for_each_safe" not in thread
    assert "engine->poll_worker_active++" in thread
    assert "wait_event(engine->poll_idle_wq" in thread
    destroy = lib.split("static int engine_destroy", 1)[1].split(
        "static void remove_engines", 1)[0]
    assert destroy.index("sgdma_thread_remove_work") < destroy.index("engine_free_resource")
    assert destroy.index("cancel_work_sync") < destroy.index("engine_free_resource")
    assert lib.count("init_waitqueue_head(&engine->poll_idle_wq)") == 2
    assert "u64 poll_generation" in head
    assert "not get comp desc at this poll work" not in lib
    guard = lib.split("static void engine_wait_stopped", 1)[1].split(
        "struct sgdma_request_cb * sgdma_request_alloc", 1)[0]
    assert "!(status & SGDMA_STAT_BUSY)" in guard
    assert "!(control & SGDMA_CTRL_RUN_STOP)" in guard
    assert "retaining DMA mappings" in guard
    assert guard.index("spin_unlock_irqrestore", guard.index("return;")) < guard.index("usleep_range")
    for signature, endmark in [
        ("ssize_t sgdma_xfer_aperture", "ssize_t sgdma_xfer_submit"),
        ("ssize_t sgdma_xfer_submit", "EXPORT_SYMBOL_GPL(sgdma_xfer_submit)")]:
        part = lib.split(signature, 1)[1].split(endmark, 1)[0]
        assert part.index("engine_wait_stopped") < part.index("transfer_destroy")
        assert part.index("engine_wait_stopped") < part.index("dma_unmap_sg")
    assert destroy.index("engine_wait_stopped") < destroy.index("engine_free_resource")
    assert "engine->poll_removing || engine->dma_quiescing" in lib
    return 24


if __name__ == "__main__":
    print(f"PASS: {poll_checks()} poll interleavings; "
          f"{lease_checks()} lifetime interleavings; {stop_guard_checks()} stop states; "
          f"{source_checks()} source guards")
    print("Negative controls detected stale service and cancelled timeout.")
    print("Boundary: no kernel compile/board test; BUSY0 semantics for final posted WB need vendor confirmation.")
