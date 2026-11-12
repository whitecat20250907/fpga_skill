//////////////////////////////////////////////////////////////
//  Copyright(c) 2011-2024 Anlogic, Inc.
//  All Right Reserved.
//////////////////////////////////////////////////////////////
//  Company       : Anlogic
//  Filename      : axil_anal.v
//  Author        : dongyu.jiang
//  Last Modified : 2025-09-30 10:06:46
//  Create        : 2024-08-14
//  Description   : Initial version. v1.0
//
///////////////////////////////////////////////////////////////
// `ifdef DEBUG_MODE
// 	`include "para_def.vh"
// `endif

module axil_anal(
    input   wire            core_clk,
    input   wire            core_rst_n,

    input   wire   [31:0]   m_axil_awaddr_i,
    input   wire   [2:0]    m_axil_awprot_i,
    input   wire            m_axil_awvalid_i,
    output  wire            m_axil_awready_o,
    input   wire   [31:0]   m_axil_wdata_i,
    input   wire   [3:0]    m_axil_wstrb_i,
    input   wire            m_axil_wvalid_i,
    output  wire            m_axil_wready_o,
    output  wire            m_axil_bvalid_o,
    output  wire   [1:0]    m_axil_bresp_o,
    input   wire            m_axil_bready_i,
    input   wire   [31:0]   m_axil_araddr_i,
    input   wire   [2:0]    m_axil_arprot_i,
    input   wire            m_axil_arvalid_i,
    output  wire            m_axil_arready_o,
    output  wire   [31:0]   m_axil_rdata_o,
    output  wire   [1:0]    m_axil_rresp_o,
    output  wire            m_axil_rvalid_o,
    input   wire            m_axil_rready_i,

    output  wire   [7:0]    axil_wshake_o,
    output  wire   [31:0]   axil_wdata_o,
    output  wire   [31:0]   axil_waddr_o,
    output  wire   [7:0]    axil_rshake_o,
    output  wire   [31:0]   axil_raddr_o,
    input   wire   [32*8-1:0]  axil_rdata_i,

    //user interrupt
    output  wire   [31:0]   usr_irq_req_o,
    input   wire   [31:0]   usr_irq_evt_i,

	output  wire   [1:0]    usr_lp0rw_cmd_o,
    output  wire            usr_cfgrw_cmd_o,
    output  wire            c2h_h2c_start_o,
    output  wire            c2h_h2c_mode_o,
    output  wire [3:0]      axil_wstrb_o,
    output  wire            bar_read_valid_o,
    output wire bar_write_valid_o
);

// Revision37: one independently buffered AW and W, one held B/R response.
// The original eight application banks and all legacy output ports remain.
reg aw_pending, w_pending, write_ack_pending, read_pending;
reg [31:0] aw_capture, w_capture, ar_capture;
reg [3:0] strobe_capture;
reg bvalid, rvalid;
reg [31:0] rdata;
reg [7:0] write_bank;
reg committed_write;
reg [31:0] write_address, write_data;
reg [3:0] write_strobe;
reg [31:0] usr_irq_req;
reg [1:0] usr_lp0rw_cmd;
reg usr_cfgrw_cmd, c2h_h2c_start, c2h_h2c_mode;
(* ram_style = "bram" *) reg [31:0] axi_reg_ram [0:511];

function [7:0] bank_mask;
    input [31:0] address;
    begin
        bank_mask=0;
        // BAR0 is1MiB. Its assigned absolute base[31:20] is not an offset.
        if(address[19:16]==0) begin
            case(address[15:8])
                8'h00:bank_mask=8'h01; 8'h01:bank_mask=8'h02;
                8'h02:bank_mask=8'h04; 8'h03:bank_mask=8'h08;
                8'h10:bank_mask=8'h10; 8'h11:bank_mask=8'h20;
                8'h12:bank_mask=8'h40; 8'h13:bank_mask=8'h80;
                default:bank_mask=0;
            endcase
        end
    end
endfunction
function [8:0] word_index;
    input [31:0] address;
    reg [2:0] bank;
    begin
        case(address[15:8])
            8'h00:bank=0;8'h01:bank=1;8'h02:bank=2;8'h03:bank=3;
            8'h10:bank=4;8'h11:bank=5;8'h12:bank=6;default:bank=7;
        endcase
        word_index={bank,address[7:2]};
    end
endfunction
wire write_commit=aw_pending && w_pending && !bvalid && !write_ack_pending;
wire [7:0] captured_bank=bank_mask(aw_capture);
assign m_axil_awready_o=core_rst_n && !aw_pending && !bvalid && !write_ack_pending;
assign m_axil_wready_o=core_rst_n && !w_pending && !bvalid && !write_ack_pending;
assign m_axil_bvalid_o=bvalid;
assign m_axil_bresp_o=2'b00;
// A committed write and its downstream CSR pulse retire before a later read.
// Unpaired AW or W alone does not block the independent read channel.
assign m_axil_arready_o=core_rst_n && !read_pending && !rvalid &&
                       !write_commit && !write_ack_pending;
assign m_axil_rvalid_o=rvalid;
assign m_axil_rdata_o=rdata;
assign m_axil_rresp_o=2'b00;
assign axil_wshake_o=write_bank;
assign axil_waddr_o=write_address;
assign axil_wdata_o=write_data;
assign axil_wstrb_o=write_strobe;
// These legacy application read strobes were unused in the original source.
assign axil_rshake_o=8'd0;
assign axil_raddr_o=ar_capture;
assign bar_read_valid_o=read_pending;
assign bar_write_valid_o=committed_write;
assign usr_irq_req_o=usr_irq_req;
assign usr_lp0rw_cmd_o=usr_lp0rw_cmd;
assign usr_cfgrw_cmd_o=usr_cfgrw_cmd;
assign c2h_h2c_start_o=c2h_h2c_start;
assign c2h_h2c_mode_o=c2h_h2c_mode;
integer lane;
always @(posedge core_clk or negedge core_rst_n) begin
    if(!core_rst_n) begin
        aw_pending<=0;w_pending<=0;write_ack_pending<=0;bvalid<=0;
        aw_capture<=0;w_capture<=0;strobe_capture<=0;
        committed_write<=0;write_bank<=0;write_address<=0;write_data<=0;write_strobe<=0;
        usr_irq_req<=0;usr_lp0rw_cmd<=0;usr_cfgrw_cmd<=0;
        c2h_h2c_start<=0;c2h_h2c_mode<=0;
    end else begin
        write_bank<=0;
        committed_write<=0;
        if(m_axil_awvalid_i && m_axil_awready_o) begin
            aw_capture<=m_axil_awaddr_i;aw_pending<=1;
        end
        if(m_axil_wvalid_i && m_axil_wready_o) begin
            w_capture<=m_axil_wdata_i;strobe_capture<=m_axil_wstrb_i;w_pending<=1;
        end
        if(write_commit) begin
            committed_write<=|strobe_capture;
            aw_pending<=0;w_pending<=0;write_ack_pending<=1;
            write_address<=aw_capture;write_strobe<=strobe_capture;
            write_data<={
                (strobe_capture[3]?w_capture[31:24]:8'd0),
                (strobe_capture[2]?w_capture[23:16]:8'd0),
                (strobe_capture[1]?w_capture[15:8]:8'd0),
                (strobe_capture[0]?w_capture[7:0]:8'd0)};
            write_bank<=|strobe_capture ? captured_bank : 8'd0;
            if(captured_bank[0] && strobe_capture[0] && aw_capture[7:0]==8'h20) begin
                usr_lp0rw_cmd<=w_capture[1:0];usr_cfgrw_cmd<=w_capture[2];
            end
            if(captured_bank[0] && strobe_capture[0] && aw_capture[7:0]==8'h24) begin
                c2h_h2c_start<=w_capture[0];c2h_h2c_mode<=w_capture[1];
            end
            if(captured_bank[0] && aw_capture[7:0]==8'h28)
                for(lane=0;lane<4;lane=lane+1)
                    if(strobe_capture[lane])usr_irq_req[lane*8+:8]<=w_capture[lane*8+:8];
        end
        // Downstream CSR consumers process write_bank on this same edge.
        if(write_ack_pending) begin write_ack_pending<=0;bvalid<=1;end
        if(bvalid && m_axil_bready_i)bvalid<=0;
    end
end
genvar byte_lane;
generate for(byte_lane=0;byte_lane<4;byte_lane=byte_lane+1)begin: byte_write
    always @(posedge core_clk) begin
        if(core_rst_n && write_commit && |captured_bank && strobe_capture[byte_lane])
            axi_reg_ram[word_index(aw_capture)][byte_lane*8+:8]<=w_capture[byte_lane*8+:8];
    end
end endgenerate
// Single registered response. Neither new address inputs nor live IRQ/events
// can change RDATA while RVALID waits for RREADY.
always @(posedge core_clk or negedge core_rst_n) begin
    if(!core_rst_n) begin read_pending<=0;ar_capture<=0;rvalid<=0;end
    else begin
        if(m_axil_arvalid_i && m_axil_arready_o) begin
            ar_capture<=m_axil_araddr_i;read_pending<=1;
        end
        if(read_pending)begin read_pending<=0;rvalid<=1;end
        if(rvalid && m_axil_rready_i)rvalid<=0;
    end
end
always @(posedge core_clk) begin
    if(read_pending) begin
        if(ar_capture[19:0]==20'h00028)rdata<=usr_irq_evt_i;
        else if(|bank_mask(ar_capture))rdata<=axi_reg_ram[word_index(ar_capture)];
        else rdata<=32'd0;
    end
end
endmodule
