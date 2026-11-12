// Latest-value command mailbox. In-flight data is immutable until accepted;
// writes during backpressure coalesce into one pending, complete command.
// rst_n must assert for BOTH domains on either domain's clock/reset failure.
// Source inputs describe the desired state, and are replayed once on restart.
module cdc_latest_command #(
    parameter WIDTH=8,
    parameter [WIDTH-1:0] INITIAL_VALUE=0
)(
    input wire rst_n,
    input wire src_clk,
    input wire src_load,
    input wire [WIDTH-1:0] src_value,
    output wire src_busy,
    input wire dst_clk,
    input wire dst_ready,
    output reg dst_valid,
    output reg [WIDTH-1:0] dst_value
);
(* async_reg="true" *) reg [1:0] src_reset_meta,dst_reset_meta;
reg src_up,dst_up;
always @(posedge src_clk or negedge rst_n)
    if(!rst_n) begin src_reset_meta<=0;src_up<=0;end
    else begin src_reset_meta<={src_reset_meta[0],1'b1};src_up<=src_reset_meta[1];end
always @(posedge dst_clk or negedge rst_n)
    if(!rst_n) begin dst_reset_meta<=0;dst_up<=0;end
    else begin dst_reset_meta<={dst_reset_meta[0],1'b1};dst_up<=dst_reset_meta[1];end

reg [WIDTH-1:0] held_value,pending_value,last_input;
reg dirty,request;
reg acknowledge;
(* async_reg="true" *) reg [1:0] acknowledge_sync,request_sync;
always @(posedge src_clk or negedge src_up)
    if(!src_up) acknowledge_sync<=0;
    else acknowledge_sync<={acknowledge_sync[0],acknowledge};
always @(posedge dst_clk or negedge dst_up)
    if(!dst_up) request_sync<=0;
    else request_sync<={request_sync[0],request};

wire input_changed=src_load || (src_value!=last_input);
assign src_busy=(request!=acknowledge_sync[1]) || dirty;
always @(posedge src_clk or negedge src_up) begin
    if(!src_up) begin
        held_value<=INITIAL_VALUE;pending_value<=INITIAL_VALUE;
        last_input<=INITIAL_VALUE;dirty<=1;request<=0;
    end else begin
        if(input_changed) begin
            pending_value<=src_value;last_input<=src_value;dirty<=1;
        end
        if(request==acknowledge_sync[1] && (dirty || input_changed)) begin
            held_value<=input_changed ? src_value : pending_value;
            request<=~request;dirty<=0;
        end
    end
end

// An additional destination clock after the private synchronizer pair
// gives the held bundle settling time. No independent bit synchronizers.
reg settling;
always @(posedge dst_clk or negedge dst_up) begin
    if(!dst_up) begin
        acknowledge<=0;settling<=0;dst_valid<=0;dst_value<=INITIAL_VALUE;
    end else begin
        if(dst_valid && dst_ready) begin
            dst_valid<=0;acknowledge<=request_sync[1];
        end
        if(!dst_valid && !settling && request_sync[1]!=acknowledge)
            settling<=1;
        if(settling) begin
            dst_value<=held_value;dst_valid<=1;settling<=0;
        end
    end
end
endmodule
