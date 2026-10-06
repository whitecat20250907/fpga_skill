`timescale 1ns/1ps
// Actual routed PHY09b netlist only. No source-clock, data, reset, or delay force.
// The 25-byte scheduler is the tiny retention sink, not a CSI-2 parser.
module tb_csi_local_clock09_sdf;
    parameter integer PHASE=0;
    reg sys_clk=0,hs_clk=0,running=1;
    reg [3:0] serial=0;
    wire uart_tx;
    always #20 sys_clk=~sys_clk;
    initial begin
        #(PHASE*1.122+0.071);
        forever begin #1.122; if(running)hs_clk=~hs_clk;end
    end
    td_local09_top dut(.sys_clk(sys_clk),.mipi_clk_hs_rx_p(hs_clk),
                       .mipi_data_hs_p(serial),.uart_tx(uart_tx));
    wire byte_clk=dut.\phy/O_hs_div_clk_created_gclkinst_auto_created_sclk_s_2_l_bk1_sclk_outnet ;
    wire pad_pclk=dut.\phy/w_pad_clk_x2 ;
    wire global_pclk=dut.\phy/w_hs_clk_x2_created_gclkinst_auto_created_sclk_s_2_l_bk3_sclk_outnet ;
    wire sclk=dut.\phy/w_hs_clk_x4 ;
    wire byte_reset_n=dut.\phy/hs_reset_sync [1];
    wire sampler_reset=dut.\phy/sampler_reset_sync [2];
    wire [31:0] raw=dut.\phy/w_rx_byte_data ;
    wire [31:0] aligned=dut.\phy/w_rx_byte_data_align ;
    wire [3:0] valid=dut.\phy/w_rx_byte_data_align_vaild ;
    integer received=0,packets=0,lane_bytes=0,k;
    integer insertion_checks=0;
    real t_external,t_sclk,t_local,t_global;
    reg checking=0,test_done=0;
    function automatic [7:0] golden(input integer lane,input integer index);
        if(index==0)golden=8'hb8;
        else golden=8'h20+lane*17+(index-1)*5;
    endfunction
    always @(posedge hs_clk)t_external=$realtime;
    always @(posedge sclk)t_sclk=$realtime;
    always @(posedge pad_pclk)t_local=$realtime;
    always @(posedge global_pclk)begin
        t_global=$realtime;
        if(byte_reset_n===1 && t_global>t_local && t_sclk>t_external)
            insertion_checks=insertion_checks+1;
    end
    // Observe after the routed register Q propagation, before the next byte edge.
    always @(posedge byte_clk)begin
        #1.3;
        if(checking && valid!==0)begin
            if(valid!==4'hf)$fatal(1,"SDF lane phase differs phase=%0d valid=%b time=%0t",PHASE,valid,$time);
            if(received>=25)$fatal(1,"SDF duplicated output byte");
            for(k=0;k<4;k=k+1)begin
                if(aligned[k*8+:8]!==golden(k,received))
                    $fatal(1,"SDF absolute serial mismatch phase=%0d packet=%0d byte=%0d lane=%0d expected=%h got=%h raw=%h",PHASE,packets,received,k,golden(k,received),aligned[k*8+:8],raw);
                lane_bytes=lane_bytes+1;
            end
            received=received+1;
            if(received==25)checking=0;
        end
    end
    task automatic flush_zero;
        begin
            serial=0;checking=0;
            repeat(80)@(negedge byte_clk);
            if(raw!==0||valid!==0)$fatal(1,"SDF zero flush has stale data raw=%h valid=%b",raw,valid);
            if(dut.\phy/I_wait_for_sync !==1)$fatal(1,"Tiny sink did not restore sync search");
        end
    endtask
    task automatic send_packet(input integer pause_at);
        integer idx,bitidx,lane,guard;
        begin
            flush_zero();received=0;checking=1;
            for(idx=0;idx<25;idx=idx+1)begin
                for(bitidx=0;bitidx<8;bitidx=bitidx+1)begin
                    @(hs_clk);#0.56;
                    for(lane=0;lane<4;lane=lane+1)serial[lane]=(golden(lane,idx)>>bitidx)&1;
                end
                if(idx==pause_at)begin #0.15;running=0;#50;running=1;end
            end
            @(hs_clk);#0.56;serial=0;
            guard=0;
            while(checking && guard<40)begin @(negedge byte_clk);guard=guard+1;end
            if(received!=25)$fatal(1,"SDF incomplete bytes=%0d",received);
            packets=packets+1;
        end
    endtask
    initial begin
        wait(byte_reset_n===1 && sampler_reset===0);
        repeat(10)@(negedge byte_clk);
        send_packet(-1);send_packet(10);send_packet(-1);flush_zero();
        if(dut.accepted!==16'd75)$fatal(1,"Tiny sink count wrong accepted=%0d",dut.accepted);
        if(insertion_checks<100)$fatal(1,"Nonzero clock insertion was not observed checks=%0d",insertion_checks);
        $display("PASS CSI_LOCAL_CLOCK09_SDF phase=%0d packets=%0d lane_bytes=%0d insertion_checks=%0d local_global_delta=%0.3fns",PHASE,packets,lane_bytes,insertion_checks,t_global-t_local);
        test_done=1;$finish;
    end
    initial begin #30000;$fatal(1,"SDF test timeout reset=%b sampler=%b raw=%h valid=%b",byte_reset_n,sampler_reset,raw,valid);end
endmodule
