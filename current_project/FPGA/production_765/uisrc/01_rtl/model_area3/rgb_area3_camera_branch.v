// Passive branch at the already accepted selected51 ISP RGB4 beat.
// No ready output to the camera. Independent loss/restart and C2H1 backpressure.
`timescale 1ns/1ps
`default_nettype none
module rgb_area3_camera_branch #(parameter WIDTH=1920,HEIGHT=1080)(
 input wire[1:0]view_select,
 output wire view_fire,view_sof,view_eol,view_eof,
 output wire[95:0]view_rgb,output wire[2:0]view_count,
 output wire[31:0]view_id,output wire[63:0]view_tick,
 input wire clk,rst_n,enable,supported,input wire tap_fire,tap_sof,tap_eol,
 input wire [95:0] tap_isp,
 output wire m_valid,input wire m_ready,output wire [127:0] m_data,
 output wire m_sof,m_eol,m_eof,output wire [31:0] m_id,output wire [63:0] m_tick,
 output reg [31:0] source_frames,output wire [31:0] complete_frames,abort_frames,overflows,
 output wire error
);
 localparam [12:0] SMALL_HEIGHT=HEIGHT/3;
 reg [63:0] ticks,frame_tick;
 always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin ticks<=0;frame_tick<=0;source_frames<=0;end
 else begin ticks<=ticks+1'b1;if(tap_fire&&tap_sof)begin source_frames<=source_frames+1'b1;frame_tick<=ticks;end end
 end
 wire run=rst_n&&enable&&supported;
 wire [95:0] rgb3;rgb4_isp_to_rgb3 binding(.isp_rgb(tap_isp),.rgb3(rgb3));
 wire qv,qr,qs,ql;wire[95:0] qrgb;wire[31:0] qid;wire[63:0] qt;
 rgb4_frame_drop_fifo #(.ADDRESS_BITS(9)) queue(
 .clk(clk),.rst_n(run),.tap_fire(tap_fire&&enable&&supported),.tap_rgb(rgb3),.tap_sof(tap_sof),.tap_eol(tap_eol),
 .tap_frame_id(source_frames+(tap_sof?32'd1:32'd0)),.tap_source_ns(tap_sof?ticks:frame_tick),
 .out_valid(qv),.out_ready(qr),.out_rgb(qrgb),.out_sof(qs),.out_eol(ql),.out_frame_id(qid),.out_source_ns(qt),.overflow_events(overflows));
 wire av,ar,asof,al,ae,aerr;wire[47:0] argb;wire[1:0] ac;wire[31:0] aid;wire[63:0] at;
 rgb_area3_4ppc #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) area(
 .clk(clk),.rst_n(run),.in_valid(qv),.in_ready(qr),.in_rgb(qrgb),.in_sof(qs),.in_eol(ql),.in_frame_id(qid),.in_source_ns(qt),
 .out_valid(av),.out_ready(ar),.out_rgb(argb),.out_count(ac),.out_sof(asof),.out_eol(al),.out_eof(ae),.out_frame_id(aid),.out_source_ns(at),
 .frame_completions(complete_frames),.frame_aborts(abort_frames),.framing_error(aerr));
 wire berr,beof;
 wire tv,tr;wire [147:0] td;wire tl;wire[8:0] tf;
 axis_stream_fifo #(.DATA_WIDTH(148),.DEPTH(256),.ADDR_BITS(8)) tensor_elastic(
 .clk(clk),.rst_n(run),.s_tvalid(av),.s_tready(ar),.s_tdata({at,aid,al,asof,ac,argb}),.s_tlast(ae),
 .m_tvalid(tv),.m_tready(tr),.m_tdata(td),.m_tlast(tl),.fill_level(tf));
 rgb_tensor_bundle bundle(.view_select(view_select),.view_fire(view_fire),.view_sof(view_sof),.view_eol(view_eol),.view_eof(view_eof),
 .view_rgb(view_rgb),.view_count(view_count),.view_id(view_id),.view_tick(view_tick),
.clk(clk),.rst_n(run),.s_valid(tv),.s_ready(tr),.s_rgb(td[47:0]),.s_count(td[49:48]),.s_sof(td[50]),.s_eol(td[51]),.s_id(td[83:52]),.s_tick(td[147:84]),
 .m_valid(m_valid),.m_ready(m_ready),.m_data(m_data),.m_sof(m_sof),.m_eof(beof),.m_id(m_id),.m_tick(m_tick),.error(berr));
 assign error=aerr||berr;
 assign m_eof=beof&&!error;
 assign m_eol=1'b0;

endmodule
`default_nettype wire
