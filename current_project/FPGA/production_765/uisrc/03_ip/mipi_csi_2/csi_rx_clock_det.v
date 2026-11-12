// CSI clock presence uses a Gray counter, not sampled asynchronous clock levels.
// Short MIPI horizontal/vertical blanking must not reset RAW/Bayer line state.
module csi_rx_clock_det #(
    parameter LOSS_CYCLES=15000000, // 100 ms at this design's 150 MHz reference
    parameter ACQUIRE_EDGES=4
)(input I_ref_clock,I_ext_clock,I_enable,I_reset_in,output reg O_reset_out);
    // Root assertion is asynchronous; each functional counter releases locally.
    (* async_reg="true" *) reg [2:0] source_reset_release,reference_reset_release;
    always @(posedge I_ext_clock or negedge I_reset_in)
        if(!I_reset_in) source_reset_release<=0;
        else source_reset_release<={source_reset_release[1:0],1'b1};
    always @(posedge I_ref_clock or negedge I_reset_in)
        if(!I_reset_in) reference_reset_release<=0;
        else reference_reset_release<={reference_reset_release[1:0],1'b1};
    wire source_reset_n=source_reset_release[2];
    wire reference_reset_n=reference_reset_release[2];
    reg [5:0] source_count;
    // Register Gray in its source domain: a combinational binary encoder can
    // briefly toggle several CDC bits when the binary counter carries.
    reg [5:0] source_gray;
    wire [5:0] source_next=source_count+1'b1;
    (* async_reg="true" *) reg [5:0] gray_s1,gray_s2;
    (* async_reg="true" *) reg enable_s1,enable_s2;
    reg [5:0] last_gray;
    reg [$clog2(LOSS_CYCLES+1)-1:0] loss_count;
    reg [3:0] acquire_count;
    always @(posedge I_ext_clock or negedge source_reset_n)
        if(!source_reset_n) begin source_count<=0;source_gray<=0;end
        else begin
            source_count<=source_next;
            source_gray<=(source_next>>1)^source_next;
        end
    always @(posedge I_ref_clock or negedge reference_reset_n) begin
        if(!reference_reset_n) begin
            gray_s1<=0;gray_s2<=0;last_gray<=0;
            enable_s1<=0;enable_s2<=0;loss_count<=0;acquire_count<=0;O_reset_out<=0;
        end else begin
            gray_s1<=source_gray;gray_s2<=gray_s1;last_gray<=gray_s2;
            enable_s1<=I_enable;enable_s2<=enable_s1;
            if(!enable_s2) begin
                loss_count<=0;acquire_count<=0;O_reset_out<=0;
            end else if(gray_s2!=last_gray) begin
                loss_count<=0;
                if(!O_reset_out) begin
                    if(acquire_count==ACQUIRE_EDGES-1) O_reset_out<=1;
                    else acquire_count<=acquire_count+1'b1;
                end
            end else if(loss_count>=LOSS_CYCLES-1) begin
                O_reset_out<=0;acquire_count<=0;
            end else loss_count<=loss_count+1'b1;
        end
    end
endmodule
