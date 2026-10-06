`timescale 1ns/1ps
// One of four parallel F3 line engines, 480 gray pixels per lane/row.
// Capture and encode use opposite ping-pong banks. Delta is reversible:
// d[0]=gray[0], d[i]=gray[i]-gray[i-1] modulo 256.
// LZ77 profile: literal bytes except 0xFF -> FF 00; offset-one matches
// length 3..130 -> FF (80|(length-3)). Stored fallback prevents expansion.
module lz1_lane_engine #(
    parameter N=480
)(
    input wire clk,rst_n,
    input wire cap_valid,
    input wire [7:0] cap_gray,
    input wire [8:0] cap_addr,
    input wire cap_line_start,
    input wire cap_bank,
    input wire start,
    input wire start_bank,
    output reg busy,
    output reg done,
    output reg done_bank,
    output reg done_mode,
    output reg [8:0] done_length,
    input wire read_bank,
    input wire read_mode,
    input wire [8:0] read_addr,
    output wire [7:0] read_data,
    input wire [8:0] read_addr_next,
    output wire [7:0] read_data_next
);
    localparam IDLE=2'd0,CHECK=2'd1,EXTEND=2'd2;
    reg [1:0] state;
    reg [7:0] raw0[0:N-1],raw1[0:N-1];
    reg [7:0] even0[0:(N/2)-1],odd0[0:(N/2)-1];
    reg [7:0] even1[0:(N/2)-1],odd1[0:(N/2)-1];
    reg [7:0] prev_gray;
    reg encode_bank;
    reg [8:0] pos,out_ptr;
    reg [7:0] run_value,run_length;
    wire [7:0] delta=cap_gray-(cap_line_start?8'd0:prev_gray);
    wire [9:0] p1={1'b0,pos}+10'd1;
    wire [9:0] p2={1'b0,pos}+10'd2;
    wire [9:0] pext={1'b0,pos}+{2'b0,run_length};
    wire [7:0] b0=encode_bank?raw1[pos]:raw0[pos];
    wire [7:0] b1=encode_bank?raw1[p1[8:0]]:raw0[p1[8:0]];
    wire [7:0] b2=encode_bank?raw1[p2[8:0]]:raw0[p2[8:0]];
    wire [7:0] bp=encode_bank?raw1[pos-1'b1]:raw0[pos-1'b1];
    wire [7:0] bext=encode_bank?raw1[pext[8:0]]:raw0[pext[8:0]];
    wire match3=(pos!=0 && pos+9'd2<N &&
                 b0==bp && b1==b0 && b2==b0);
    wire [8:0] literal_new_ptr=out_ptr+((b0==8'hFF)?9'd2:9'd1);
    wire [8:0] match_new_ptr=out_ptr+9'd2;
    wire [9:0] match_new_pos={1'b0,pos}+{2'b0,run_length};
    wire [7:0] token=8'h80 | (run_length-8'd3);
    assign read_data=read_mode
        ? (read_bank
           ? (read_addr[0]?odd1[read_addr[8:1]]:even1[read_addr[8:1]])
           : (read_addr[0]?odd0[read_addr[8:1]]:even0[read_addr[8:1]]))
        : (read_bank?raw1[read_addr]:raw0[read_addr]);
    assign read_data_next=read_mode
        ? (read_bank
           ? (read_addr_next[0]?odd1[read_addr_next[8:1]]:even1[read_addr_next[8:1]])
           : (read_addr_next[0]?odd0[read_addr_next[8:1]]:even0[read_addr_next[8:1]]))
        : (read_bank?raw1[read_addr_next]:raw0[read_addr_next]);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            prev_gray<=0; state<=IDLE; encode_bank<=0;
            pos<=0;out_ptr<=0;run_value<=0;run_length<=0;
            busy<=0;done<=0;done_bank<=0;done_mode<=0;done_length<=0;
        end else begin
            done<=0;
            if (cap_valid) begin
                if (cap_bank) raw1[cap_addr]<=delta;
                else raw0[cap_addr]<=delta;
                prev_gray<=cap_gray;
            end
            case (state)
                IDLE: if (start) begin
                    encode_bank<=start_bank;
                    pos<=0;out_ptr<=0;busy<=1;state<=CHECK;
                end
                CHECK: begin
                    if (match3) begin
                        run_value<=b0;
                        run_length<=8'd3;
                        state<=EXTEND;
                    end else if (literal_new_ptr>=N) begin
                        // Stop early: stored data already occupy N bytes.
                        done<=1;done_bank<=encode_bank;
                        done_mode<=0;done_length<=N;
                        busy<=0;state<=IDLE;
                    end else begin
                        if (encode_bank) begin
                            if (out_ptr[0]) odd1[out_ptr[8:1]]<=b0;
                            else even1[out_ptr[8:1]]<=b0;
                            if (b0==8'hFF) begin
                                if (out_ptr[0]) even1[literal_new_ptr[8:1]]<=0;
                                else odd1[out_ptr[8:1]]<=0;
                            end
                        end else begin
                            if (out_ptr[0]) odd0[out_ptr[8:1]]<=b0;
                            else even0[out_ptr[8:1]]<=b0;
                            if (b0==8'hFF) begin
                                if (out_ptr[0]) even0[literal_new_ptr[8:1]]<=0;
                                else odd0[out_ptr[8:1]]<=0;
                            end
                        end
                        out_ptr<=literal_new_ptr;
                        pos<=pos+1'b1;
                        if (pos==N-1) begin
                            done<=1;done_bank<=encode_bank;
                            done_mode<=1;done_length<=literal_new_ptr;
                            busy<=0;state<=IDLE;
                        end
                    end
                end
                EXTEND: begin
                    if (run_length<130 && pext<N && bext==run_value)
                        run_length<=run_length+1'b1;
                    else if (match_new_ptr>=N) begin
                        done<=1;done_bank<=encode_bank;
                        done_mode<=0;done_length<=N;
                        busy<=0;state<=IDLE;
                    end else begin
                        if (encode_bank) begin
                            if (out_ptr[0]) begin
                                odd1[out_ptr[8:1]]<=8'hFF;
                                even1[match_new_ptr[8:1]]<=token;
                            end else begin
                                even1[out_ptr[8:1]]<=8'hFF;
                                odd1[out_ptr[8:1]]<=token;
                            end
                        end else begin
                            if (out_ptr[0]) begin
                                odd0[out_ptr[8:1]]<=8'hFF;
                                even0[match_new_ptr[8:1]]<=token;
                            end else begin
                                even0[out_ptr[8:1]]<=8'hFF;
                                odd0[out_ptr[8:1]]<=token;
                            end
                        end
                        out_ptr<=match_new_ptr;
                        pos<=match_new_pos[8:0];
                        if (match_new_pos>=N) begin
                            done<=1;done_bank<=encode_bank;
                            done_mode<=1;done_length<=match_new_ptr;
                            busy<=0;state<=IDLE;
                        end else state<=CHECK;
                    end
                end
                default: state<=IDLE;
            endcase
        end
    end
endmodule
