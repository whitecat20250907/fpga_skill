`timescale 1ns/1ps
// Bounded eye-window analysis, local coordinates only. Capture -> current
// 8%-quantile -> replicated-border binary3x3 opening ->4-connected CCL ->
// largest-component moments. Full ROI remains on the independent crop stream.
// Analysis has a finite cycle budget. Busy windows are explicitly counted and
// skipped rather than applying CSI backpressure or labelling stale results new.
module hci02_eye_measure #(
 parameter MAX_WIDTH=256,MAX_HEIGHT=128,MAX_LABELS=32,MAX_RUNS_ROW=64,
 parameter PERCENT=8,ANALYSIS_LIMIT=MAX_WIDTH*MAX_HEIGHT*32+2048,
 parameter MAX_PIXELS=MAX_WIDTH*MAX_HEIGHT,ABITS=$clog2(MAX_PIXELS+1),LBITS=$clog2(MAX_LABELS+1)
)(
 input wire clk,rst_n,input wire s_valid,input wire [7:0] s_gray,
 input wire s_sof,s_last,s_eof,input wire [15:0] s_x,s_y,s_origin_x,s_origin_y,s_width,s_height,
 input wire [31:0] s_frame_id,s_config_sequence,input wire [63:0] s_time_us,input wire [7:0] s_flags,
 output wire s_ready,input wire m_ready,output reg m_valid,output reg [767:0] m_result,
 output reg [31:0] received_windows,completed_windows,skipped_windows,label_overflows,deadline_overflows,errors
);
 localparam CLEAR=0,IDLE=1,CAPTURE=2,WAIT_SAD=3,THRESHOLD=4,MP_PRIME=5,MP_READ=6,
  CCL_INIT=7,CCL_READ=8,CCL_EXAM=9,ROOT_LEFT=10,ROOT_TOP=11,CCL_ASSIGN=12,
  CCL_NEXT=13,SELECT=14,REPORT=15,HOLD=16,TARGET_DIVIDE=17;
 reg [4:0] state;
 reg [15:0] histogram[0:63];reg [5:0] bin;
 reg current_bank,previous_bank,previous_valid,frame_bad,drop_window;
 reg [15:0] width,height,origin_x,origin_y,previous_width,previous_height,previous_origin_x,previous_origin_y;
 reg [31:0] frame_id,config_sequence,previous_frame_id,total_pixels,captured_pixels;
 reg [63:0] time_us;
 reg [15:0] cap_x,cap_y;
 reg [31:0] sum_y,sum_y2,bright,dark,sad,work_cycles;
 reg [7:0] minimum,maximum;
 reg sad_available,sad_pending,sad_bank;reg [7:0] sad_gray;
 reg [31:0] cdf,target;
 reg [8:0] threshold;
 // Exactly (total_pixels*PERCENT+99)/100, one quotient bit per cycle.
 // Avoid the measured 27-level single-cycle constant division path.
 reg [31:0] division_numerator,division_quotient;
 reg [6:0] division_remainder;reg [4:0] division_step;
 wire [7:0] division_shifted={division_remainder,division_numerator[31]};
 wire division_subtract=division_shifted>=8'd100;
 wire [7:0] division_next_remainder=division_subtract?division_shifted-8'd100:division_shifted;
 wire [31:0] division_next_quotient={division_quotient[30:0],division_subtract};
 reg morph_phase,morph_valid,morph_sof,morph_last,morph_input_done;
 reg [ABITS-1:0] morph_read_position,morph_write_position;
 reg [15:0] morph_x,morph_y;
 reg [15:0] px,py;reg [ABITS-1:0] position;
 wire [7:0] image_q0,image_q1;wire eroded_q,opened_q;
 wire [7:0] previous_q=sad_bank?image_q1:image_q0;
 wire [7:0] analysis_q=current_bank?image_q1:image_q0;
 reg [31:0] global_area;
 reg [LBITS-1:0] line_labels[0:MAX_WIDTH-1],parent[0:MAX_LABELS];
 reg [31:0] area[0:MAX_LABELS],sx[0:MAX_LABELS],sy[0:MAX_LABELS],sxx[0:MAX_LABELS],sxy[0:MAX_LABELS],syy[0:MAX_LABELS];
 reg [15:0] xmin[0:MAX_LABELS],xmax[0:MAX_LABELS],ymin[0:MAX_LABELS],ymax[0:MAX_LABELS];
 reg [LBITS-1:0] left_label,top_label,root_l,root_t,root_pointer,labels_used,best_label,scan_label;
 reg [31:0] best_area,second_area,component_count;
 reg [15:0] runs_in_row;
 reg [31:0] quality;
 wire first=s_valid&&s_sof&&state==IDLE&&!drop_window;
 wire receive=s_valid&&!drop_window&&(state==CAPTURE||first);
 assign s_ready=1'b1;
 wire [ABITS-1:0] capture_address=first?0:captured_pixels[ABITS-1:0];
 wire capture_bank=first?!previous_bank:current_bank;
 wire [15:0] capture_width=first?s_width:width,capture_height=first?s_height:height;
 wire [31:0] capture_total=capture_width*capture_height;
 wire legal_geometry=s_width!=0&&s_height!=0&&s_width<=MAX_WIDTH&&s_height<=MAX_HEIGHT;
 wire same_previous=previous_valid&&s_width==previous_width&&s_height==previous_height&&
  s_origin_x==previous_origin_x&&s_origin_y==previous_origin_y&&s_frame_id==previous_frame_id+1'b1;
 wire expect_last=(first?16'd0:cap_x)==capture_width-1'b1;
 wire expect_eof=expect_last&&(first?16'd0:cap_y)==capture_height-1'b1;
 wire receive_bad=(!first&&s_sof)||s_x!=(first?0:cap_x)||s_y!=(first?0:cap_y)||
  s_last!=expect_last||s_eof!=expect_eof||!s_flags[3]||(!first&&(s_width!=width||s_height!=height||
  s_origin_x!=origin_x||s_origin_y!=origin_y||s_frame_id!=frame_id||s_config_sequence!=config_sequence||s_time_us!=time_us));
 wire morph_bit=morph_phase?eroded_q:({1'b0,analysis_q}<threshold);
 wire morph_ready,morph_out,morph_out_valid,morph_out_sof,morph_out_last,morph_out_eof;
 wire [31:0] morph_errors;
 wire morph_advance=!morph_valid||morph_ready;
 wire morph_read=state==MP_READ&&!morph_input_done&&morph_advance;
 wire morph_reset_n=rst_n&&(state==MP_PRIME||state==MP_READ);
 hci02_binary_spatial #(.MAX_WIDTH(MAX_WIDTH),.MAX_HEIGHT(MAX_HEIGHT))u_opening(
  .clk(clk),.rst_n(morph_reset_n),.s_data(morph_bit),.s_valid(morph_valid),
  .s_sof(morph_sof),.s_last(morph_last),.s_op(morph_phase),.s_width(width),.s_height(height),.s_ready(morph_ready),
  .m_ready(1'b1),.m_data(morph_out),.m_valid(morph_out_valid),.m_sof(morph_out_sof),
  .m_last(morph_out_last),.m_eof(morph_out_eof),.errors(morph_errors));
 wire [LBITS-1:0] winner=root_l==0?root_t:(root_t==0?root_l:(root_l<root_t?root_l:root_t));
 wire [LBITS-1:0] loser=root_l==0||root_t==0||root_l==root_t?0:(root_l<root_t?root_t:root_l);
 wire [31:0] xx=px*px,xy=px*py,yy=py*py;
 wire [31:0] merged_area=area[winner]+(loser!=0?area[loser]:0)+1'b1;
 wire [15:0] merged_xmin=loser!=0&&xmin[loser]<xmin[winner]?xmin[loser]:xmin[winner];
 wire [15:0] merged_xmax=loser!=0&&xmax[loser]>xmax[winner]?xmax[loser]:xmax[winner];
 wire [15:0] merged_ymin=loser!=0&&ymin[loser]<ymin[winner]?ymin[loser]:ymin[winner];
 wire [15:0] merged_ymax=loser!=0&&ymax[loser]>ymax[winner]?ymax[loser]:ymax[winner];
 wire [ABITS-1:0] image_read_address=receive?capture_address:morph_read_position;
 // Explicit logicalERAM prevents failed implicit read-FF/reset absorption.
 localparam MEM_BITS=$clog2(MAX_PIXELS),MEM_DEPTH=1<<MEM_BITS;
 wire image_read_enable=rst_n&&(receive||morph_read)&&image_read_address<MAX_PIXELS;
 hci02_eram_sdp #(.DATA_WIDTH(8),.DEPTH(MEM_DEPTH),.ADDR_BITS(MEM_BITS))u_image0(
  .clk(clk),.wr_en(rst_n&&receive&&!capture_bank&&capture_address<MAX_PIXELS),.wr_addr(capture_address[MEM_BITS-1:0]),.wr_data(s_gray),
  .rd_en(image_read_enable),.rd_addr(image_read_address[MEM_BITS-1:0]),.rd_data(image_q0));
 hci02_eram_sdp #(.DATA_WIDTH(8),.DEPTH(MEM_DEPTH),.ADDR_BITS(MEM_BITS))u_image1(
  .clk(clk),.wr_en(rst_n&&receive&&capture_bank&&capture_address<MAX_PIXELS),.wr_addr(capture_address[MEM_BITS-1:0]),.wr_data(s_gray),
  .rd_en(image_read_enable),.rd_addr(image_read_address[MEM_BITS-1:0]),.rd_data(image_q1));
 hci02_eram_sdp #(.DATA_WIDTH(1),.DEPTH(MEM_DEPTH),.ADDR_BITS(MEM_BITS))u_eroded(
  .clk(clk),.wr_en(rst_n&&state==MP_READ&&morph_out_valid&&!morph_phase),.wr_addr(morph_write_position[MEM_BITS-1:0]),.wr_data(morph_out),
  .rd_en(rst_n&&morph_read),.rd_addr(morph_read_position[MEM_BITS-1:0]),.rd_data(eroded_q));
 hci02_eram_sdp #(.DATA_WIDTH(1),.DEPTH(MEM_DEPTH),.ADDR_BITS(MEM_BITS))u_opened(
  .clk(clk),.wr_en(rst_n&&state==MP_READ&&morph_out_valid&&morph_phase),.wr_addr(morph_write_position[MEM_BITS-1:0]),.wr_data(morph_out),
  .rd_en(rst_n&&state==CCL_READ),.rd_addr(position[MEM_BITS-1:0]),.rd_data(opened_q));
 reg [31:0] report_quality,report_area;integer k;
 always @*begin
  report_quality=quality;
  report_area=(quality[6]||quality[7]||quality[10])?0:best_area;
  if(report_area==0)report_quality[1]=1;
  if(maximum-minimum<16)report_quality[2]=1;
  if(bright*10>total_pixels)report_quality[3]=1;
  if(report_area*100<total_pixels||report_area*100>total_pixels*60)report_quality[4]=1;
  if(report_area!=0&&(xmin[best_label]==0||ymin[best_label]==0||xmax[best_label]==width-1||ymax[best_label]==height-1))report_quality[5]=1;
  if(!sad_available)report_quality[8]=1;
  if(second_area!=0&&second_area*2>=report_area)report_quality[9]=1;
  report_quality[0]=(report_quality&32'hfffffefe)==0;
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=CLEAR;bin<=0;m_valid<=0;m_result<=0;
   current_bank<=0;previous_bank<=0;previous_valid<=0;frame_bad<=0;drop_window<=0;
   width<=0;height<=0;origin_x<=0;origin_y<=0;previous_width<=0;previous_height<=0;previous_origin_x<=0;previous_origin_y<=0;
   frame_id<=0;config_sequence<=0;previous_frame_id<=0;time_us<=0;total_pixels<=0;captured_pixels<=0;cap_x<=0;cap_y<=0;
   sum_y<=0;sum_y2<=0;bright<=0;dark<=0;sad<=0;minimum<=255;maximum<=0;
   sad_available<=0;sad_pending<=0;sad_bank<=0;sad_gray<=0;cdf<=0;target<=0;threshold<=0;work_cycles<=0;
   division_numerator<=0;division_quotient<=0;division_remainder<=0;division_step<=0;
   morph_phase<=0;morph_valid<=0;morph_sof<=0;morph_last<=0;morph_input_done<=0;
   morph_read_position<=0;morph_write_position<=0;morph_x<=0;morph_y<=0;
   px<=0;py<=0;position<=0;global_area<=0;
   left_label<=0;top_label<=0;root_l<=0;root_t<=0;root_pointer<=0;labels_used<=0;best_label<=0;scan_label<=0;
   best_area<=0;second_area<=0;component_count<=0;runs_in_row<=0;quality<=0;
   received_windows<=0;completed_windows<=0;skipped_windows<=0;label_overflows<=0;deadline_overflows<=0;errors<=0;
  end else begin
   sad_pending<=receive&&(first?same_previous:sad_available);
   if(sad_pending)sad<=sad+(sad_gray>previous_q?sad_gray-previous_q:previous_q-sad_gray);
   if(s_valid&&s_sof)begin
    received_windows<=received_windows+1'b1;
    if(state!=IDLE)begin skipped_windows<=skipped_windows+1'b1;drop_window<=!s_eof;end
   end
   if(s_valid&&s_eof&&drop_window)drop_window<=0;
   if(receive)begin
    sad_gray<=s_gray;sad_bank<=previous_bank;
    histogram[s_gray[7:2]]<=histogram[s_gray[7:2]]+1'b1;
    if(first)begin
     state<=CAPTURE;current_bank<=!previous_bank;width<=s_width;height<=s_height;
     origin_x<=s_origin_x;origin_y<=s_origin_y;frame_id<=s_frame_id;config_sequence<=s_config_sequence;time_us<=s_time_us;
     total_pixels<=capture_total;captured_pixels<=1;cap_x<=s_last?0:1;cap_y<=s_last?1:0;
     sum_y<=s_gray;sum_y2<=s_gray*s_gray;bright<=s_gray>=240;dark<=s_gray<=16;
     minimum<=s_gray;maximum<=s_gray;sad<=0;sad_available<=same_previous;
     frame_bad<=!legal_geometry||receive_bad;quality<=0;work_cycles<=0;threshold<=0;
     global_area<=0;best_area<=0;second_area<=0;best_label<=0;component_count<=0;
     if(!legal_geometry)errors[1]<=1;
    end else begin
     captured_pixels<=captured_pixels+1'b1;
     if(s_last)begin cap_x<=0;cap_y<=cap_y+1'b1;end else cap_x<=cap_x+1'b1;
     sum_y<=sum_y+s_gray;sum_y2<=sum_y2+s_gray*s_gray;
     bright<=bright+(s_gray>=240);dark<=dark+(s_gray<=16);
     if(s_gray<minimum)minimum<=s_gray;if(s_gray>maximum)maximum<=s_gray;
     if(receive_bad)frame_bad<=1;
    end
    if(receive_bad)errors[0]<=1;
    if(s_eof)begin
     state<=WAIT_SAD;
     previous_bank<=capture_bank;previous_width<=capture_width;previous_height<=capture_height;
     previous_origin_x<=first?s_origin_x:origin_x;previous_origin_y<=first?s_origin_y:origin_y;
     previous_frame_id<=first?s_frame_id:frame_id;
     previous_valid<=!(first?!legal_geometry:frame_bad)&&!receive_bad&&(first?1:captured_pixels+1)==capture_total;
     if((first?1:captured_pixels+1)!=capture_total)begin frame_bad<=1;errors[0]<=1;end
    end
   end
   case(state)
    CLEAR:begin
     histogram[bin]<=0;
     if(bin==63)begin bin<=0;state<=IDLE;end else bin<=bin+1'b1;
    end
    WAIT_SAD:begin
     if(frame_bad)begin quality[7]<=1;state<=REPORT;end
     else begin
      bin<=0;cdf<=0;division_numerator<=total_pixels*PERCENT+32'd99;
      division_quotient<=0;division_remainder<=0;division_step<=0;state<=TARGET_DIVIDE;
     end
    end
    TARGET_DIVIDE:begin
     division_numerator<={division_numerator[30:0],1'b0};
     division_quotient<=division_next_quotient;division_remainder<=division_next_remainder[6:0];
     if(division_step==31)begin target<=division_next_quotient;state<=THRESHOLD;end
     else division_step<=division_step+1'b1;
    end
    THRESHOLD:begin
     cdf<=cdf+histogram[bin];
     if(cdf+histogram[bin]>=target)begin
      threshold<=({3'd0,bin}<<2)+9'd4;px<=0;py<=0;position<=0;morph_phase<=0;state<=MP_PRIME;
     end else if(bin==63)begin quality[7]<=1;errors[0]<=1;state<=REPORT;end
     else bin<=bin+1'b1;
    end
    MP_PRIME:begin
     morph_valid<=0;morph_input_done<=0;morph_read_position<=0;morph_write_position<=0;morph_x<=0;morph_y<=0;state<=MP_READ;
    end
    MP_READ:begin
     if(morph_advance)begin
      morph_valid<=morph_read;
      if(morph_read)begin
       morph_sof<=morph_read_position==0;morph_last<=morph_x==width-1;
       if(morph_read_position==total_pixels-1)morph_input_done<=1;
       else begin
        morph_read_position<=morph_read_position+1'b1;
        if(morph_x==width-1)begin morph_x<=0;morph_y<=morph_y+1'b1;end else morph_x<=morph_x+1'b1;
       end
      end
     end
     if(morph_out_valid)begin
      morph_write_position<=morph_write_position+1'b1;
      if(morph_phase&&morph_out)global_area<=global_area+1'b1;
      if(morph_out_eof)begin
       morph_valid<=0;px<=0;py<=0;position<=0;
       if(morph_phase)begin scan_label<=0;state<=CCL_INIT;end
       else begin morph_phase<=1;state<=MP_PRIME;end
      end
     end
     if(morph_errors!=0)begin quality[7]<=1;errors[2]<=1;state<=REPORT;end
    end
    CCL_INIT:begin
     parent[scan_label]<=scan_label;area[scan_label]<=0;sx[scan_label]<=0;sy[scan_label]<=0;
     sxx[scan_label]<=0;sxy[scan_label]<=0;syy[scan_label]<=0;
     xmin[scan_label]<=0;xmax[scan_label]<=0;ymin[scan_label]<=0;ymax[scan_label]<=0;
     if(scan_label==MAX_LABELS)begin labels_used<=0;left_label<=0;runs_in_row<=0;state<=CCL_READ;end
     else scan_label<=scan_label+1'b1;
    end
    CCL_READ:begin top_label<=py==0?0:line_labels[px];state<=CCL_EXAM;end
    CCL_EXAM:begin
     if(!opened_q)begin line_labels[px]<=0;left_label<=0;state<=CCL_NEXT;end
     else if(left_label==0&&runs_in_row>=MAX_RUNS_ROW)begin
      quality[6]<=1;label_overflows<=label_overflows+1'b1;state<=REPORT;
     end else begin
      if(left_label==0)runs_in_row<=runs_in_row+1'b1;
      root_pointer<=left_label;state<=ROOT_LEFT;
     end
    end
    ROOT_LEFT:begin
     if(root_pointer==0||parent[root_pointer]==root_pointer)begin root_l<=root_pointer;root_pointer<=top_label;state<=ROOT_TOP;end
     else root_pointer<=parent[root_pointer];
    end
    ROOT_TOP:begin
     if(root_pointer==0||parent[root_pointer]==root_pointer)begin root_t<=root_pointer;state<=CCL_ASSIGN;end
     else root_pointer<=parent[root_pointer];
    end
    CCL_ASSIGN:begin
     if(winner==0)begin
      if(labels_used==MAX_LABELS)begin quality[6]<=1;label_overflows<=label_overflows+1'b1;state<=REPORT;end
      else begin
       labels_used<=labels_used+1'b1;parent[labels_used+1'b1]<=labels_used+1'b1;
       area[labels_used+1'b1]<=1;sx[labels_used+1'b1]<=px;sy[labels_used+1'b1]<=py;
       sxx[labels_used+1'b1]<=xx;sxy[labels_used+1'b1]<=xy;syy[labels_used+1'b1]<=yy;
       xmin[labels_used+1'b1]<=px;xmax[labels_used+1'b1]<=px;ymin[labels_used+1'b1]<=py;ymax[labels_used+1'b1]<=py;
       line_labels[px]<=labels_used+1'b1;left_label<=labels_used+1'b1;state<=CCL_NEXT;
      end
     end else begin
      area[winner]<=merged_area;sx[winner]<=sx[winner]+(loser!=0?sx[loser]:0)+px;
      sy[winner]<=sy[winner]+(loser!=0?sy[loser]:0)+py;
      sxx[winner]<=sxx[winner]+(loser!=0?sxx[loser]:0)+xx;
      sxy[winner]<=sxy[winner]+(loser!=0?sxy[loser]:0)+xy;
      syy[winner]<=syy[winner]+(loser!=0?syy[loser]:0)+yy;
      xmin[winner]<=px<merged_xmin?px:merged_xmin;xmax[winner]<=px>merged_xmax?px:merged_xmax;
      ymin[winner]<=py<merged_ymin?py:merged_ymin;ymax[winner]<=py>merged_ymax?py:merged_ymax;
      if(loser!=0)begin parent[loser]<=winner;area[loser]<=0;end
      line_labels[px]<=winner;left_label<=winner;state<=CCL_NEXT;
     end
    end
    CCL_NEXT:begin
     if(position==total_pixels-1)begin scan_label<=1;state<=SELECT;end
     else begin
      position<=position+1'b1;
      if(px==width-1)begin px<=0;py<=py+1'b1;left_label<=0;runs_in_row<=0;end else px<=px+1'b1;
      state<=CCL_READ;
     end
    end
    SELECT:begin
     if(labels_used==0)state<=REPORT;
     else begin
      if(parent[scan_label]==scan_label&&area[scan_label]!=0)begin
       component_count<=component_count+1'b1;
       if(area[scan_label]>best_area)begin second_area<=best_area;best_area<=area[scan_label];best_label<=scan_label;end
       else if(area[scan_label]>second_area)second_area<=area[scan_label];
      end
      if(scan_label==labels_used)state<=REPORT;else scan_label<=scan_label+1'b1;
     end
    end
    REPORT:begin
     m_result<=0;m_result[31:0]<=report_quality;m_result[63:32]<=frame_id;m_result[95:64]<=config_sequence;
     m_result[159:96]<=time_us;m_result[191:160]<={origin_y,origin_x};m_result[223:192]<={height,width};
     m_result[255:224]<={23'd0,threshold};m_result[287:256]<=report_area;
     if(report_area!=0)begin
      m_result[319:288]<=sx[best_label];m_result[351:320]<=sy[best_label];m_result[383:352]<=sxx[best_label];
      m_result[415:384]<=sxy[best_label];m_result[447:416]<=syy[best_label];
      m_result[479:448]<={ymin[best_label],xmin[best_label]};m_result[511:480]<={ymax[best_label],xmax[best_label]};
     end
     m_result[543:512]<=sad_available?sad:0;m_result[575:544]<=dark;m_result[607:576]<=bright;
     m_result[639:608]<=sum_y;m_result[671:640]<=sum_y2;m_result[703:672]<=global_area;
     m_result[735:704]<=component_count;m_result[767:736]<=work_cycles;
     m_valid<=1;completed_windows<=completed_windows+1'b1;state<=HOLD;
    end
    HOLD:if(m_valid&&m_ready)begin m_valid<=0;bin<=0;state<=CLEAR;end
    default:;
   endcase
   if((state>=WAIT_SAD&&state<=SELECT)||state==TARGET_DIVIDE)begin
    work_cycles<=work_cycles+1'b1;
    if(work_cycles>=ANALYSIS_LIMIT-1)begin quality[10]<=1;deadline_overflows<=deadline_overflows+1'b1;state<=REPORT;end
   end
  end
 end
 // synthesis translate_off
 initial if(MAX_WIDTH<1||MAX_WIDTH>256||MAX_HEIGHT<1||MAX_HEIGHT>128||MAX_LABELS<1||MAX_LABELS>63||MAX_RUNS_ROW<1||PERCENT<1||PERCENT>50)$fatal(1,"Unsupported eye measurement bounds");
 // synthesis translate_on
endmodule
