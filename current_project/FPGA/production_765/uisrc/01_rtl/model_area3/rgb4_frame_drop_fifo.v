// Passive accepted-beat tap. There is deliberately no ready signal to source.
// On overflow discard unread queue contents and ignore source until a new SOF.
// An already offered output remains stable until accepted; it may be a partial
// old frame. The area3/host consumer must commit only a complete EOF frame.
// Keep one memory slot unused to avoid same-address read/write at full turnover.
`timescale 1ns/1ps
`default_nettype none
module rgb4_frame_drop_fifo #(
    parameter ADDRESS_BITS=5
)(
    input wire clk,rst_n,
    input wire tap_fire,
    input wire [95:0] tap_rgb,
    input wire tap_sof,tap_eol,
    input wire [31:0] tap_frame_id,
    input wire [63:0] tap_source_ns,
    output reg out_valid,
    input wire out_ready,
    output reg [95:0] out_rgb,
    output reg out_sof,out_eol,
    output reg [31:0] out_frame_id,
    output reg [63:0] out_source_ns,
    output wire dropping,
    output wire [ADDRESS_BITS:0] queued_beats,
    output reg [31:0] source_sofs,queued_sofs,overflow_events,
    output reg [31:0] discarded_source_beats,discarded_queued_beats
);
    localparam DEPTH=1<<ADDRESS_BITS;
    localparam CAPACITY=DEPTH-1;
    (* ram_style="bram(min_area)" *) reg [193:0] memory[0:DEPTH-1];
    reg [ADDRESS_BITS-1:0] write_pointer,read_pointer;
    reg [ADDRESS_BITS:0] count;
    reg forwarding;
    wire advance=!out_valid || out_ready;
    wire pop=advance && count!=0;
    wire eligible=forwarding || tap_sof;
    wire overflow=tap_fire && eligible && count==CAPACITY && !pop;
    wire push=tap_fire && eligible && !overflow;
    assign queued_beats=count;
    assign dropping=!forwarding;

    always @(posedge clk) begin
        if(rst_n) begin
            if(push) memory[write_pointer]<={tap_source_ns,tap_frame_id,tap_sof,tap_eol,tap_rgb};
            if(pop)
                {out_source_ns,out_frame_id,out_sof,out_eol,out_rgb}<=memory[read_pointer];
        end
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            write_pointer<=0;read_pointer<=0;count<=0;forwarding<=0;out_valid<=0;
            source_sofs<=0;queued_sofs<=0;overflow_events<=0;
            discarded_source_beats<=0;discarded_queued_beats<=0;
        end else begin
            if(tap_fire && tap_sof) source_sofs<=source_sofs+1'b1;
            if(tap_fire && !push) discarded_source_beats<=discarded_source_beats+1'b1;
            if(advance) out_valid<=pop;
            if(overflow) begin
                write_pointer<=0;read_pointer<=0;count<=0;forwarding<=0;
                overflow_events<=overflow_events+1'b1;
                discarded_queued_beats<=discarded_queued_beats+count;
            end else begin
                case({push,pop})
                    2'b10:count<=count+1'b1;
                    2'b01:count<=count-1'b1;
                    default:count<=count;
                endcase
                if(push) begin
                    write_pointer<=write_pointer+1'b1;
                    if(tap_sof) begin forwarding<=1;queued_sofs<=queued_sofs+1'b1;end
                end
                if(pop) read_pointer<=read_pointer+1'b1;
            end
        end
    end
endmodule
`default_nettype wire
