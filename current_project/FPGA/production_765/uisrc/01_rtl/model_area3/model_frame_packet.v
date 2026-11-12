// Independent C2H1 stream. 64-byte header, RGB3 payload, 16-byte CRC/commit footer.
// One bounded host credit admits one complete source frame. Main video is unrelated.
`timescale 1ns/1ps
`default_nettype none
module model_frame_packet #(parameter WIDTH=640,HEIGHT=360,TIMEOUT=125000,PAYLOAD_SIZE=WIDTH*HEIGHT*3,FORMAT=32'h33424752)(
 input wire clk,rst_n,enable,credit,admit_frame,input wire [63:0] epoch,
 input wire s_valid,output wire s_ready,input wire [127:0] s_data,
 input wire s_sof,s_eof,input wire [31:0] s_id,input wire [63:0] s_tick,
 output wire m_valid,input wire m_ready,output reg [127:0] m_data,output wire m_last,
 output reg pending,output wire busy,output reg [31:0] completed,aborted,dropped
);
 localparam BYTES=PAYLOAD_SIZE;
 localparam [31:0] PAYLOAD_BYTES=BYTES,STRIDE=WIDTH*3;
 localparam [15:0] IMAGE_W=WIDTH,IMAGE_H=HEIGHT;
 localparam IDLE=0,H0=1,H1=2,H2=3,H3=4,DATA=5,FOOT=6;
 reg [2:0] state;reg held,held_eof;reg [127:0] payload;
 reg [31:0] id,bytes,crc,idle_ticks,status;reg [63:0] tick,active_epoch;
 function [31:0] crc128;
 input [31:0] seed;input [127:0] data;
 integer bitno;reg [31:0] c;
 begin c=seed;for(bitno=0;bitno<128;bitno=bitno+1)c=(c>>1)^((c[0]^data[bitno])?32'hedb88320:32'd0);crc128=c;end
 endfunction
 assign busy=state!=IDLE;
 assign s_ready=state==IDLE?1'b1:(state==DATA&&(!held||m_ready)&&!(held&&held_eof)&&!(held&&bytes+16>=BYTES));
 assign m_valid=state!=IDLE&&(state!=DATA||held);
 assign m_last=state==FOOT;
 always @*begin
 m_data=0;
 case(state)
 H0:m_data={id,PAYLOAD_BYTES,32'h00010040,32'h31463341}; // A3F1
 H1:m_data={32'd0,STRIDE,IMAGE_H,IMAGE_W,FORMAT};
 H2:m_data={active_epoch,tick};
 H3:m_data={32'd0,32'd125000000,64'd0};
 DATA:m_data=payload;
 FOOT:m_data={32'h31444e45,bytes,status,~crc};
 default:m_data=0;
 endcase
 end
 always @(posedge clk or negedge rst_n)begin
 if(!rst_n)begin state<=IDLE;held<=0;held_eof<=0;payload<=0;pending<=0;completed<=0;aborted<=0;dropped<=0;id<=0;bytes<=0;crc<=32'hffffffff;idle_ticks<=0;status<=0;tick<=0;active_epoch<=0;end
 else begin
 // enable may be removed only by a quiesced host; active packet still retires.
 if(!enable&&state==IDLE)pending<=0;else if(credit&&enable)pending<=1;
 if(state==IDLE)begin
 held<=0;idle_ticks<=0;
 if(s_valid&&s_sof)begin
 if(enable&&pending&&admit_frame)begin
 state<=H0;pending<=0;payload<=s_data;held<=1;held_eof<=s_eof;
 id<=s_id;tick<=s_tick;active_epoch<=epoch;bytes<=0;crc<=32'hffffffff;status<=0;
 end else dropped<=dropped+1'b1;
 end
 end else if(state>=H0&&state<=H3)begin
 if(m_ready)state<=state==H3?DATA:state+1'b1;
 end else if(state==DATA)begin
 if(held&&m_ready)begin
 held<=0;crc<=crc128(crc,payload);bytes<=bytes+16;idle_ticks<=0;
 if(held_eof||bytes+16>=BYTES)begin state<=FOOT;status<=(held_eof&&bytes+16==BYTES)?1:2;end
 end
 if(s_valid&&s_ready)begin
 idle_ticks<=0;
 if(s_sof||s_id!=id||s_tick!=tick)begin state<=FOOT;status<=4;held<=0;end
 else begin held<=1;held_eof<=s_eof;payload<=s_data;end
 end else if(!held)begin
 if(idle_ticks==TIMEOUT-1)begin state<=FOOT;status<=8;end else idle_ticks<=idle_ticks+1'b1;
 end
 end else if(state==FOOT&&m_ready)begin
 if(status==1)completed<=completed+1'b1;else aborted<=aborted+1'b1;
 state<=IDLE;held<=0;
 end
 end
 end
 // synthesis translate_off
 initial if(BYTES%16!=0)$fatal(1,"Payload must be 16-byte aligned");
 // synthesis translate_on
endmodule
`default_nettype wire
