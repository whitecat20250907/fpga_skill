`timescale 1ns/1ps
module tb_csi_clock;
 reg refclk=0,extclk=0,rst=0,en=0,runclk=1;
 always #5 refclk=~refclk;
 // Identical frequency and phase reproduces aliasing in the vendor level sampler.
 always #5 if(runclk)extclk=~extclk;else extclk=0;
 wire released;
 csi_rx_clock_det #(.LOSS_CYCLES(150),.ACQUIRE_EDGES(4)) dut(refclk,extclk,en,rst,released);
 initial begin
  repeat(5)@(negedge refclk);rst=1;en=1;
  repeat(30)@(negedge refclk);if(!released)$fatal(1,"equal-frequency clock falsely missing");
  repeat(400)@(negedge refclk);if(!released)$fatal(1,"clock-level alias resets receiver");
  runclk=0;repeat(100)@(negedge refclk);if(!released)$fatal(1,"short packet blanking resets receiver");
  runclk=1;repeat(30)@(negedge refclk);if(!released)$fatal(1,"blanking recovery");
  runclk=0;repeat(180)@(negedge refclk);if(released)$fatal(1,"real missing clock undetected");
  runclk=1;repeat(30)@(negedge refclk);if(!released)$fatal(1,"clock recovery failed");
  en=0;repeat(6)@(negedge refclk);if(released)$fatal(1,"disabled receiver not reset");
  $display("PASS CSI clock: aliasing, blanking tolerance, loss detection, recovery, disable");$finish;
 end
 initial begin #20000;$fatal(1,"CSI clock test timeout");end
endmodule
