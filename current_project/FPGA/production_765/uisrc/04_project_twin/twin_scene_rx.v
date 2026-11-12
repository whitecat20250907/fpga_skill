`timescale 1ns/1ps
`default_nettype none
// HFT2/HFT3 app-profile transport-independent parser. No malformed, bad-CRC or stale packet
// publishes geometry or advances the accepted sequence. RAM stays owned
// until scene_release; a rendered/front framebuffer is entirely separate.
module twin_scene_rx #(
 parameter integer RX_TIMEOUT_MS=20,parameter integer EXTERNAL_ARRIVAL=0
)(
 input wire clk,input wire rst,input wire [31:0] now_ms,
 input wire rx_valid,input wire [7:0] rx_data,output wire rx_ready,
 input wire scene_release,output reg scene_valid,
 output reg [7:0] vertex_count,edge_count,triangle_count,
 output reg [4:0] valid_mask,output reg fixture,
 output reg [79:0] source_ages,output reg [159:0] group_offsets,
 output reg [63:0] source_hand_ns,source_face_ns,session_epoch,scene_sequence,
 output reg [31:0] source_capture_sequence,eye_metrics,arrival_ms,
 output reg [1:0] actor_slot,output reg [31:0] actor_track_id,ui_status,display_generation,
 output reg [7:0] classification_confidence,trajectory_points,association_flags,
 output reg [4:0] invalidate_mask,output reg epoch_changed,
 input wire [6:0] vertex_addr,output reg [50:0] vertex_data,
 input wire [6:0] edge_addr,output reg [17:0] edge_data,
 input wire [5:0] triangle_addr,output reg [25:0] triangle_data,
 output reg [31:0] accepted_packets,crc_errors,format_errors,sequence_errors,
 input wire [31:0] rx_ingress_ms
);
 localparam SYNC=0,HEADER=1,VERTEX=2,EDGE=3,TRIANGLE=4,CRC=5,HOLD=6;
 reg [2:0] state;reg [1:0] magic_step,crc_byte;
 reg [6:0] header_pos;reg [7:0] record_index,trace_vertices;reg [2:0] record_byte;
 reg [7:0] h[0:119];reg [7:0] rec[0:6];reg [2:0] group_map[0:127];
 reg [50:0] vertices[0:127];reg [17:0] edges[0:127];reg [25:0] triangles[0:63];
 reg [31:0] crc,received_crc,last_byte_ms,packet_arrival_ms;
 reg bad_payload,epoch_bound;
 wire [31:0] silence_ms=now_ms-last_byte_ms;
 wire [15:0] payload_length={h[13],h[12]};
 wire [15:0] calculated_length={8'b0,h[7]}*16'd8+{8'b0,h[8]}*16'd4+{8'b0,h[9]}*16'd4;
 wire [63:0] h_epoch={h[31],h[30],h[29],h[28],h[27],h[26],h[25],h[24]};
 wire [63:0] h_seq={h[39],h[38],h[37],h[36],h[35],h[34],h[33],h[32]};
 wire [63:0] h_previous={h[91],h[90],h[89],h[88],h[87],h[86],h[85],h[84]};
 wire initial_binding=!epoch_bound && h_epoch!=0 && (!h[5][1] || h_previous==0);
 wire same_binding=epoch_bound && h_epoch==session_epoch && !h[5][1] && h_seq>scene_sequence;
 wire new_binding=epoch_bound && h_epoch!=0 && h_epoch!=session_epoch && h[5][1] && h_previous==session_epoch && h_seq==0;
 wire binding_ok=initial_binding || same_binding || new_binding;
 reg header_ok;
 integer k;
 always @* begin
  header_ok=((h[4]==2 && h[6]==112)||(h[4]==3 && h[6]==120)) && (h[5]&8'hfc)==0 && h[7]<=128 && h[8]<=128 && h[9]<=64 &&
    (h[10]&8'he0)==0 && (h[11]==1 || h[11]==2) && payload_length==calculated_length && (h[4]==2 ? rx_data==0 : h[111]==0);
  if(h[4]==3 && h[10][4] && {rx_data,h[118],h[117],h[116],h[115],h[114],h[113],h[112]}==64'd0)header_ok=0;
  for(k=92;k<96;k=k+1)if(h[k]!=0)header_ok=0;
  if(h[7]==0 && (h[8]!=0 || h[9]!=0))header_ok=0;
  if(!((h[100][3:0]<=5)||(h[100][3:0]==15)))header_ok=0;
  if(!((h[100][7:4]<=6)||(h[100][7:4]==15)))header_ok=0;
  if(!((h[101][3:0]<=7)||(h[101][3:0]==15)))header_ok=0;
  if(h[102][1:0]>2 || (h[102]&8'hfc)!=0 || h[103]!=0 || h[109]>48 || (h[110]&8'hf8)!=0)header_ok=0;
  // A displayed hand belongs to the explicitly registered page, never just
  // an arbitrary left/right label. IDs are session tracks, not biometrics.
  if((h[10][0] && !h[110][1]) || (h[10][1] && !h[110][2]))header_ok=0;
  if((h[10][2] || h[10][3] || h[110][1] || h[110][2]) && !h[110][0])header_ok=0;
  if(h[110][0] && {h[99],h[98],h[97],h[96]}==32'hffffffff)header_ok=0;
  if(h[10][4] && (h[102][1:0]!=1 || h[110][2:1]==0 || h[109]==0))header_ok=0;
  if(h[101][7] && (!h[101][6] || !h[101][5] || !h[110][0]))header_ok=0;
  if(h[101][6] && (!h[101][5] || !h[110][0]))header_ok=0;
  if(h[101][4] && (h[100][3:0]!=3 || h[101][3:0]>7))header_ok=0;
 end
 function [31:0] crc_byte_next;
  input [31:0] old;input [7:0] value;integer bit_number;reg [31:0] c;
  begin
   c=old^{24'd0,value};
   for(bit_number=0;bit_number<8;bit_number=bit_number+1)c=c[0]?(c>>1)^32'hedb88320:c>>1;
   crc_byte_next=c;
  end
 endfunction
 assign rx_ready=state!=HOLD;
 always @(posedge clk)begin
  vertex_data<=vertices[vertex_addr];edge_data<=edges[edge_addr];triangle_data<=triangles[triangle_addr];
 end
 integer j;
 always @(posedge clk)begin
  if(rst)begin
   state<=SYNC;magic_step<=0;crc_byte<=0;header_pos<=0;record_index<=0;record_byte<=0;trace_vertices<=0;
   crc<=32'hffffffff;received_crc<=0;bad_payload<=0;last_byte_ms<=0;packet_arrival_ms<=0;
   scene_valid<=0;vertex_count<=0;edge_count<=0;triangle_count<=0;valid_mask<=0;fixture<=0;
   source_ages<=0;group_offsets<=0;source_hand_ns<=0;source_face_ns<=0;source_capture_sequence<=32'hffffffff;
   session_epoch<=0;scene_sequence<=0;epoch_bound<=0;eye_metrics<=0;arrival_ms<=0;
   actor_slot<=1;actor_track_id<=32'hffffffff;ui_status<=32'h00000f00;display_generation<=0;
   classification_confidence<=0;trajectory_points<=0;association_flags<=0;
   invalidate_mask<=5'b11111;epoch_changed<=0;accepted_packets<=0;crc_errors<=0;format_errors<=0;sequence_errors<=0;
  end else begin
   invalidate_mask<=0;epoch_changed<=0;
   if(state==HOLD)begin
    if(scene_release)begin state<=SYNC;magic_step<=0;scene_valid<=0;end
   end else if(state!=SYNC && silence_ms>RX_TIMEOUT_MS)begin
    state<=SYNC;magic_step<=0;format_errors<=format_errors+1'b1;
    if(rx_valid && rx_data==8'h48)begin
     magic_step<=1;h[0]<=8'h48;crc<=crc_byte_next(32'hffffffff,8'h48);
     packet_arrival_ms<=(EXTERNAL_ARRIVAL ? rx_ingress_ms : now_ms);last_byte_ms<=now_ms;bad_payload<=0;
    end
   end else if(rx_valid)begin
    last_byte_ms<=now_ms;
    case(state)
     SYNC:begin
      if((magic_step==0 && rx_data==8'h48) ||
         (magic_step==1 && rx_data==8'h46) ||
         (magic_step==2 && rx_data==8'h54) ||
         (magic_step==3 && rx_data==8'h31))begin
       h[{5'd0,magic_step}]<=rx_data;
       if(magic_step==0)begin crc<=crc_byte_next(32'hffffffff,rx_data);packet_arrival_ms<=(EXTERNAL_ARRIVAL ? rx_ingress_ms : now_ms);bad_payload<=0;end
       else crc<=crc_byte_next(crc,rx_data);
       if(magic_step==3)begin state<=HEADER;header_pos<=4;magic_step<=0;end
       else magic_step<=magic_step+1'b1;
      end else if(rx_data==8'h48)begin
       magic_step<=1;h[0]<=rx_data;crc<=crc_byte_next(32'hffffffff,rx_data);packet_arrival_ms<=(EXTERNAL_ARRIVAL ? rx_ingress_ms : now_ms);bad_payload<=0;
      end else magic_step<=0;
     end
     HEADER:begin
      h[header_pos]<=rx_data;crc<=crc_byte_next(crc,rx_data);
      if(header_pos==(h[4]==3 ? 7'd119 : 7'd111))begin
       record_index<=0;record_byte<=0;crc_byte<=0;received_crc<=0;trace_vertices<=0;
       if(!header_ok)begin state<=SYNC;magic_step<=0;format_errors<=format_errors+1'b1;end
       else if(h[7]!=0)state<=VERTEX;
       else state<=CRC;
      end else header_pos<=header_pos+1'b1;
     end
     VERTEX:begin
      crc<=crc_byte_next(crc,rx_data);
      if(record_byte<7)rec[record_byte]<=rx_data;
      if(record_byte==0)begin
       group_map[record_index[6:0]]<=rx_data[2:0];if(rx_data>4)bad_payload<=1;
       if(rx_data==4)trace_vertices<=trace_vertices+1'b1;
      end
      if(record_byte==1 && rx_data!=0)bad_payload<=1;
      if(record_byte==7)begin
       vertices[record_index[6:0]]<={rec[0][2:0],rx_data,rec[6],rec[5],rec[4],rec[3],rec[2]};
       record_byte<=0;
       if(record_index+1'b1>=h[7])begin
        record_index<=0;
        if(h[8]!=0)state<=EDGE;else if(h[9]!=0)state<=TRIANGLE;else state<=CRC;
       end else record_index<=record_index+1'b1;
      end else record_byte<=record_byte+1'b1;
     end
     EDGE:begin
      crc<=crc_byte_next(crc,rx_data);if(record_byte<3)rec[record_byte]<=rx_data;
      if(record_byte==3)begin
       if(rec[0]>=h[7] || rec[1]>=h[7] || rec[2]>3 || rx_data!=0 || group_map[rec[0][6:0]]!=group_map[rec[1][6:0]])bad_payload<=1;
       edges[record_index[6:0]]<={rec[2][1:0],rec[1],rec[0]};record_byte<=0;
       if(record_index+1'b1>=h[8])begin record_index<=0;if(h[9]!=0)state<=TRIANGLE;else state<=CRC;end
       else record_index<=record_index+1'b1;
      end else record_byte<=record_byte+1'b1;
     end
     TRIANGLE:begin
      crc<=crc_byte_next(crc,rx_data);if(record_byte<3)rec[record_byte]<=rx_data;
      if(record_byte==3)begin
       if(rec[0]>=h[7] || rec[1]>=h[7] || rec[2]>=h[7] || rx_data>3 ||
          group_map[rec[0][6:0]]!=group_map[rec[1][6:0]] || group_map[rec[0][6:0]]!=group_map[rec[2][6:0]])bad_payload<=1;
       triangles[record_index[5:0]]<={rx_data[1:0],rec[2],rec[1],rec[0]};record_byte<=0;
       if(record_index+1'b1>=h[9])begin record_index<=0;state<=CRC;end else record_index<=record_index+1'b1;
      end else record_byte<=record_byte+1'b1;
     end
     CRC:begin
      received_crc[crc_byte*8 +:8]<=rx_data;
      if(crc_byte==3)begin
       state<=SYNC;magic_step<=0;
       if({rx_data,received_crc[23:0]}!=~crc)crc_errors<=crc_errors+1'b1;
       else if(bad_payload || (h[10][4] && trace_vertices!=h[109]))format_errors<=format_errors+1'b1;
       else if(!binding_ok)sequence_errors<=sequence_errors+1'b1;
       else begin
        state<=HOLD;scene_valid<=1;vertex_count<=h[7];edge_count<=h[8];triangle_count<=h[9];
        valid_mask<=h[10][4:0];fixture<=h[5][0];arrival_ms<=packet_arrival_ms;
        actor_slot<=h[11][1:0];actor_track_id<={h[99],h[98],h[97],h[96]};
        ui_status<={h[103],h[102],h[101],h[100]};display_generation<={h[107],h[106],h[105],h[104]};
        classification_confidence<=h[108];trajectory_points<=h[109];association_flags<=h[110];
        source_hand_ns<={h[47],h[46],h[45],h[44],h[43],h[42],h[41],h[40]};
        source_face_ns<={h[55],h[54],h[53],h[52],h[51],h[50],h[49],h[48]};
        source_capture_sequence<={h[59],h[58],h[57],h[56]};eye_metrics<={h[83],h[82],h[81],h[80]};
        for(j=0;j<5;j=j+1)begin
         source_ages[j*16 +:16]<={h[15+j*2],h[14+j*2]};
         group_offsets[j*32 +:32]<={h[63+j*4],h[62+j*4],h[61+j*4],h[60+j*4]};
        end
        epoch_changed<=!epoch_bound || new_binding;
        invalidate_mask<=(!epoch_bound || new_binding)?5'b11111:~h[10][4:0];
        session_epoch<=h_epoch;scene_sequence<=h_seq;epoch_bound<=1;accepted_packets<=accepted_packets+1'b1;
       end
      end else crc_byte<=crc_byte+1'b1;
     end
     default:begin state<=SYNC;magic_step<=0;end
    endcase
   end
  end
 end
endmodule
`default_nettype wire
