# FPGA5 generic held-bundle CDC reset repair

Only synthesized RTL changed: `fpga/uisrc/03_ip/vid_pipeline/csi_stats_snapshot.v`.
Ports, parameter PERIOD, 192-bit source bundle, 224-bit snapshot, busy/sequence
encoding and clock_delta arithmetic remain unchanged. The actual baseline test
entry `tb/csi_snapshot.do` now compiles this deployed file instead of the stale
`tools/csi_stats_snapshot.v` copy.

The old shared asynchronous reset was directly released into both unrelated
clocks. Each domain now has its own three-flop async-assert/synchronous-release
reset chain marked async_reg. Only the reset chains see raw rst_n; functional
source state uses src_rst_n, destination state uses dst_rst_n. A shared assertion
still clears both halves of the toggle handshake, held bus, sequence and previous
cycle count even when either clock is stopped. If source clock is stopped during
reset release, its chain and functional state remain reset. Destination may queue
one toggle request; busy then holds it until source resumes, synchronizes release
and accepts it. Both clock directions have the same behavior.

This adds six reset flops, no RAM, no data-path pipeline, and no port changes.
Functional startup waits for local synchronized reset release. PERIOD timing starts
when destination functional reset releases. The first post-reset snapshot still
has clock_delta=0; later deltas are unsigned 32-bit differences of accepted source
cycle snapshots. No fixed snapshot frequency is promised when a source is stopped
or slower than the handshake; busy continues to represent the pending request.

## Actual-source ModelSim verification

- `evidence/csi_snapshot_actual5.log`: existing tb_csi_snapshot passed coherent
  six-counter snapshots, source clock delta range, stopped-source busy and reset
  recovery. Compiler/simulator: 0 errors and 0 warnings.
- `evidence/csi_snapshot_reset5.log`: new exact-source-capture scoreboard passed
  53 coherent snapshots across two clock ratios (approximately UI24 -> user125,
  and user125 -> UART25), five reset pulses per instance. Checks include request
  in flight, source ACK before destination consumption, ACK at the final sync
  stage, pulses of 0.3..0.7ns (shorter than either clock), stop/resume without reset,
  reset while source stopped, reset while destination stopped, and delayed clock
  restart. Assertions compare every 224-bit bundle and exact clock_delta against
  the source acceptance event, reject phantom/duplicate completions and ensure no
  local reset releases before three local positive edges. 0 errors/warnings.
- `evidence/csi_snapshot_rawreset_negative5.log`: old raw-reset implementation
  with observation aliases only fails the release assertion at 1.3ns, proving the
  release check is active; it is an intentionally failing negative control.

Run from `tools/csi_snapshot_reset_trial` using ModelSim -c and either
`tb_csi_snapshot.do` or `tb_csi_snapshot_reset.do`. Tests use compressed timer
periods; they validate PERIOD counter/handshake behavior but do not run a physical
100ms board measurement. The source file is the synthesized helper, not a mirror.

## Boundaries for reuse

Digital simulation cannot reproduce analog metastability or prove physical reset
minimum pulse width. External reset must meet device requirements, both domains
must share its assertion, and counters entering src_stats must belong to src_clk
or already be synchronized. A long-stopped source retains the last completed
snapshot and busy request; it does not fabricate updates. The held-data bundle
requires its existing stable-before-ACK CDC contract and appropriate physical
routing/CDC constraints; reset repair is not permission to skip that audit.
No top-level integration, TD build, hardware capture, driver or other RTL changes
were performed in this task. Parent owns FPGA5 integration and timing/board tests.

Frozen SHA-256: `6b4c7afbe79674922ce44b4ecf13424037d5e70bf361050aea82981b7b547f63`
