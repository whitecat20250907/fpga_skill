# IMX415 clock startup candidate: digital checks

This is an independent candidate in `tools/camera_clock_startup.v`; no frozen FPGA source, TD build, board state, or driver has been changed by this task.

Inputs are `clock24`, `clock27`, `pll27_lock_raw`, `ui_lock_raw`, and `system_reset_n`. Outputs are `sensor_xclr`, `sensor_mclk`, `config_reset_n`, and `status[15:0]`. The caller must hold system reset low until the sensor power rails are valid. The existing control clock remains 24 MHz; the new native PLL clock is forwarded at its full 27 MHz rate, rather than divided by a toggle flip-flop.

Raw locks and system reset assert a three-stage reset synchronizer asynchronously. Its release and an additional eight stable control cycles precede the XCLR-low wait. XCLR remains low for at least 10 us after qualification, rises for at least 2 us before the clock request, and the request crosses into the 27 MHz domain. A falling-edge flip-flop latches the clock gate enable; the sensor clock is the source clock AND that latched enable. Its acknowledgment crosses back to the control domain and must remain high for two cycles. Another 50 us passes before configuration reset releases. Microsecond conversions are rounded up and include one guard control cycle.

Only XCLR-low reset may asynchronously clear the 27 MHz gate. Raw locks do not directly gate the clock. This permits truncation during asserted sensor reset; normal forwarding uses complete source high/low pulses. Asynchronous-reset distribution, recovery/removal, IO routing, output duty cycle, and the sensor's actual INCK source still require fresh implementation and hardware checks. This digital sequence is not a physical power or PLL model.

`status[0]` is released control reset; `[1]` qualified locks; `[2]` XCLR; `[3]` MCLK request; `[4]` synchronized gate acknowledgment; `[5]` stable acknowledgment; `[6]` released configuration reset; `[10:8]` state (0 waiting for locks, 1 XCLR low, 2 XCLR high, 3 waiting for gate acknowledgment, 4 settling, 5 running). All other bits are zero. The acknowledgment proves that an enable was latched; it does not independently measure frequency or prove continued source-clock edges. Use the separate frequency monitor for that purpose.

ModelSim 10.5 was actually run with `tools/run_camera_clock_startup.do`. The successful immutable run is `evidence/camera_clock_startup_20261004_235801_28648/simulation.log`, copied to `tools/camera_clock_startup.log`. Compilation and simulation report zero errors and warnings; `test_done=1` and `PASS CAMERA_CLOCK_STARTUP_DIGITAL_ALL` are required by the macro before exit 0.

The selfcheck covers five startup epochs, a short unqualified lock pulse, PLL lock loss mid-clock-high, UI lock loss while the control clock is stopped, asynchronous system reset at another clock phase, recovery, and a falsely asserted PLL lock with no initial 27 MHz clock. Missing startup clock leaves configuration in reset until a real gate acknowledgment arrives. The checks include XCLR-low duration, XCLR-high to first INCK, stable ACK and first INCK to configuration, source edge alignment, and all normal high/low pulse widths.

Measured ideal-clock digital intervals were:

| Interval | Minimum observed |
| --- | ---: |
| Qualified locks to XCLR high | 10.041506 us |
| XCLR high to first forwarded INCK | 2.123377 us |
| First INCK to configuration release | 50.149583 us |
| Stable gate acknowledgment to configuration release | 50.040866 us |

The bench observed 6,854 complete high pulses, 6,851 complete low intervals, and two truncations exclusively while XCLR was low. An initial failed simulation was a testbench active-region timestamp race: the derived-clock edge monitor ran before the corresponding source-clock timestamp monitor at the same simulation time. The corrected bench defers those monitors with `#0` to the inactive region; it does not advance time or relax a timing/count assertion. The failed run is retained under `evidence/camera_clock_startup_20261004_235358_504`.

Root integration must use actual pin/clock constraints and a fresh TD build. No Fmax, analog PLL lock, board power, sensor INCK routing, physical waveform, or image-color success is claimed by this selfcheck.
