`timescale 1ns/1ps
// The CSI source cannot stop. A FIFO threshold cannot reserve a whole image.
// One driver doorbell admits one SOF, only after the preceding output TLAST
// has actually handshaken. Unrequested frames are consumed without forwarding.
module vid_frame_gate #(
    parameter DATA_WIDTH=128,
    parameter FILL_BITS=12
) (
    input wire clk, rst_n, enable,
    input wire receive_credit, receive_ready, packet_done, pipeline_empty,
    input wire [DATA_WIDTH-1:0] s_tdata,
    input wire s_tvalid, s_tlast, s_frame_last, s_sof,
    output wire s_tready,
    output wire [DATA_WIDTH-1:0] m_tdata,
    output wire m_tvalid, m_frame_last,
    input wire [FILL_BITS-1:0] fifo_fill_level,
    output reg [31:0] gate_drop_count, gate_pass_count, credit_post_count,
    output reg credit_pending, packet_in_flight,
    output wire accepting_frame
);
    localparam WAIT_SOF=2'd0, PASS_FRAME=2'd1, DROP_FRAME=2'd2;
    reg [1:0] state;
    wire sof_beat=s_tvalid && s_sof;
    wire admit=enable && state!=PASS_FRAME && sof_beat &&
               credit_pending && !packet_in_flight && receive_ready &&
               pipeline_empty && fifo_fill_level=={FILL_BITS{1'b0}};
    // An unexpected SOF during PASS is a new frame, never a continuation of
    // the old packet. Suppress it; the existing guardian terminates the old
    // partial packet and the driver still reports/rejects that failure.
    wire pass=enable && ((state==PASS_FRAME && !sof_beat) || admit);
    assign s_tready=1'b1;
    assign m_tdata=s_tdata;
    assign m_tvalid=s_tvalid && pass;
    assign m_frame_last=s_frame_last && m_tvalid;
    assign accepting_frame=state==PASS_FRAME;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=WAIT_SOF;
            credit_pending<=1'b0;
            packet_in_flight<=1'b0;
            gate_drop_count<=32'd0;
            gate_pass_count<=32'd0;
            credit_post_count<=32'd0;
        end else if(!enable) begin
            state<=WAIT_SOF;
            credit_pending<=1'b0;
            packet_in_flight<=1'b0;
        end else begin
            if(packet_done) packet_in_flight<=1'b0;
            // A repeated doorbell cannot accumulate unbounded credits.
            if(receive_credit && !credit_pending) begin
                credit_pending<=1'b1;
                credit_post_count<=credit_post_count+32'd1;
            end
            if(sof_beat) begin
                if(admit) begin
                    credit_pending<=1'b0;
                    packet_in_flight<=1'b1;
                    gate_pass_count<=gate_pass_count+32'd1;
                    state<=s_frame_last ? WAIT_SOF : PASS_FRAME;
                end else begin
                    gate_drop_count<=gate_drop_count+32'd1;
                    state<=s_frame_last ? WAIT_SOF : DROP_FRAME;
                end
            end else if(s_tvalid && s_frame_last) begin
                state<=WAIT_SOF;
            end
        end
    end
endmodule
