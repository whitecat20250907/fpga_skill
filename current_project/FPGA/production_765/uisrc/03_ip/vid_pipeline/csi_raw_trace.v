// Passive frozen raw trace: immediate linear capture or error-triggered ring.
`timescale 1ns/1ps
module csi_raw_trace #(
    parameter ADDR_WIDTH=12,
    parameter POST_SAMPLES=(1<<ADDR_WIDTH)/2,
    parameter DATA_WIDTH=32
)(
    input wire rst_n,byte_clk,user_clk,
    input wire [31:0] raw_bytes,
    input wire arm_toggle,armed,trigger_mode,error_level,
    input wire [ADDR_WIDTH-1:0] read_index,
    output wire [31:0] read_data,
    output wire done,busy,
    output reg [ADDR_WIDTH-1:0] head,
    output reg [ADDR_WIDTH:0] captured_count
);
    localparam [ADDR_WIDTH:0] TRACE_DEPTH=(1<<ADDR_WIDTH);
    wire [DATA_WIDTH-1:0] memory_read;
    (* async_reg="true" *) reg [1:0] byte_reset_sync,user_reset_sync;
    (* async_reg="true" *) reg [1:0] request_sync,ack_sync;
    (* async_reg="true" *) reg [1:0] mode_sync,error_sync;
    reg request_seen,ack_toggle,capturing,request_pending,active_mode,triggered;
    reg [ADDR_WIDTH-1:0] write_index;
    reg [ADDR_WIDTH:0] valid_count,post_left;
    // Register the passive observation at its original sample edge. The RAM
    // write carries the matching address/enable one cycle later. ACK is delayed
    // by the same cycle, so software never sees an undrained final sample.
    reg [DATA_WIDTH-1:0] trace_data_q;
    reg [ADDR_WIDTH-1:0] trace_address_q;
    reg trace_write_q, trace_ack_q;
    always @(posedge byte_clk) begin
        trace_data_q <= raw_bytes[DATA_WIDTH-1:0];
        trace_address_q <= write_index;
    end
    always @(posedge byte_clk or negedge byte_reset_sync[1]) begin
        if(!byte_reset_sync[1]) begin trace_write_q<=0;trace_ack_q<=0;end
        else begin trace_write_q<=capturing;trace_ack_q<=ack_toggle;end
    end
    // synthesis translate_off
    initial if(ADDR_WIDTH<2 || POST_SAMPLES<1 || POST_SAMPLES>=(1<<ADDR_WIDTH))
        $fatal(1,"Invalid trace depth/post-trigger count");
    initial if(DATA_WIDTH<1 || DATA_WIDTH>32) $fatal(1,"Invalid trace data width");
    // synthesis translate_on
    always @(posedge byte_clk or negedge rst_n)
        if(!rst_n) byte_reset_sync<=0;
        else byte_reset_sync<={byte_reset_sync[0],1'b1};
    always @(posedge user_clk or negedge rst_n)
        if(!rst_n) user_reset_sync<=0;
        else user_reset_sync<={user_reset_sync[0],1'b1};
    always @(posedge byte_clk or negedge byte_reset_sync[1]) begin
        if(!byte_reset_sync[1]) begin
            request_sync<=0;mode_sync<=0;error_sync<=0;
            request_seen<=0;ack_toggle<=0;capturing<=0;request_pending<=0;
            active_mode<=0;triggered<=0;write_index<=0;valid_count<=0;
            post_left<=0;head<=0;captured_count<=0;
        end else begin
            request_sync<={request_sync[0],arm_toggle};
            mode_sync<={mode_sync[0],trigger_mode};
            error_sync<={error_sync[0],error_level};
            if(!capturing && !request_pending && request_sync[1]!=request_seen) begin
                request_seen<=request_sync[1];request_pending<=1;
                captured_count<=0;head<=0;
            end else if(request_pending) begin
                // Mode has one extra source cycle to settle after request CDC.
                // The UI holds it until ACK, except an explicit cancel to0.
                request_pending<=0;capturing<=1;active_mode<=mode_sync[1];
                triggered<=0;write_index<=0;valid_count<=0;post_left<=0;
            end else if(capturing) begin
                write_index<=write_index+1'b1;
                if(valid_count<TRACE_DEPTH) valid_count<=valid_count+1'b1;
                if(!active_mode) begin
                    if(&write_index) begin
                        capturing<=0;ack_toggle<=request_seen;
                        head<=0;captured_count<=TRACE_DEPTH;
                    end
                end else if(!triggered) begin
                    if(error_sync[1] || !mode_sync[1]) begin
                        triggered<=1;post_left<=POST_SAMPLES;
                    end
                end else if(post_left==1) begin
                    capturing<=0;ack_toggle<=request_seen;
                    head<=valid_count>=TRACE_DEPTH-1'b1 ? write_index+1'b1 : 0;
                    captured_count<=valid_count>=TRACE_DEPTH-1'b1 ? TRACE_DEPTH : valid_count+1'b1;
                end else post_left<=post_left-1'b1;
            end
        end
    end
    // Memory is never reset. Writer stops and holds head/count before ACK CDC.
    // UG910 sec.13: independent-clock true dual port, synchronous NOREG read.
    // Explicit primitive prevents advisory RAM inference from moving this
    // high-rate PAD observation sink into a large distributed memory tree.
    PH1_LOGIC_ERAM #(
      .DATA_WIDTH_A(DATA_WIDTH),.DATA_WIDTH_B(DATA_WIDTH),
      .ADDR_WIDTH_A(ADDR_WIDTH),.ADDR_WIDTH_B(ADDR_WIDTH),
      .DATA_DEPTH_A(1<<ADDR_WIDTH),.DATA_DEPTH_B(1<<ADDR_WIDTH),
      .MODE("DP"),.REGMODE_A("NOREG"),.REGMODE_B("NOREG"),
      .WRITEMODE_A("NORMAL"),.WRITEMODE_B("NORMAL"),
      .RESETMODE_A("ASYNC"),.RESETMODE_B("ASYNC"),.CLKMODE("ASYNC"),
      .BYTE_ENABLE(0),.FORCE_KEEP("ON"),.PACKABLE("NO"),.DEBUGGABLE("NO"),
      .IMPLEMENT("20K"),.INIT_FILE("NONE"),.FILL_ALL("NONE")) u_trace_storage (
      .dia(trace_data_q),.addra(trace_address_q),
      .cea(1'b1),.clka(byte_clk),.wea(trace_write_q && byte_reset_sync[1]),
      .bea(1'b0),.rsta(1'b0),.ocea(1'b0),.doa(),
      .dib({DATA_WIDTH{1'b0}}),.addrb(read_index),.ceb(1'b1),.clkb(user_clk),
      .web(1'b0),.beb(1'b0),.rstb(1'b0),.oceb(1'b0),.dob(memory_read),
      .ecc_sbiterr(),.ecc_dbiterr(),.ecc_sbiterrinj(1'b0),.ecc_dbiterrinj(1'b0));
    assign read_data={{(32-DATA_WIDTH){1'b0}},memory_read};
    // synthesis translate_off
    always @(posedge byte_clk) if(capturing && byte_reset_sync[1] && (raw_bytes >> DATA_WIDTH)!=0)
        $fatal(1,"Trace width contract would discard nonzero upper bits");
    // synthesis translate_on
    always @(posedge user_clk or negedge user_reset_sync[1])
        if(!user_reset_sync[1]) ack_sync<=0;
        else ack_sync<={ack_sync[0],trace_ack_q};
    assign done=armed && ack_sync[1]==arm_toggle;
    assign busy=armed && !done;
endmodule
