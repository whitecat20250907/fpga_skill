`timescale 1ns/1ps
// Actual ISP stream forks at one shared handshake into the existing full HCI01
// video and RGB-preserving three-ROI crop. Two bounded eye engines and a
// parallel quad CRC sink consume every selected crop pixel. No debug stub.
module hci02_vision_pipeline #(parameter WIDTH=1920,HEIGHT=1080,EYE_FIFO_DEPTH=1024)(
 input wire clk,rst_n,input wire [127:0] s_data,input wire s_valid,s_sof,s_last,
 output wire s_ready,input wire [13:0] hci_config,
 input wire [191:0] roi_windows,input wire [2:0] roi_enable,
 input wire [31:0] roi_sequence,input wire [15:0] roi_ttl,input wire roi_valid,
 input wire frame_tag_valid,input wire [31:0] frame_tag_id,input wire [63:0] frame_time_us,
 input wire m_ready,output wire [127:0] m_data,output wire m_valid,m_sof,m_last,m_eof,
 output wire [13:0] m_config,output wire [31:0] hci_errors,hci_frames,output wire hci_lut_valid,
 // 82little-endian32bit words. Reports are stored on actual handshakes;
 // their publication counts change on the same edge as the stored report.
 output wire [2:0] crop_valid,crop_sof,crop_last,crop_eof,
 output wire [383:0] crop_rgb,output wire [95:0] crop_gray,output wire [8:0] crop_count,
 output wire [47:0] crop_x,crop_y,crop_origin_x,crop_origin_y,crop_width,crop_height,
 output wire [31:0] crop_frame_id,crop_sequence,output wire [63:0] crop_time_us,output wire [7:0] crop_flags,
 output wire [1:0] feature_valid,output wire [1535:0] feature_result,
 output wire [63:0] feature_received,feature_skipped,feature_deadline,
 output wire [2623:0] stats,output wire [31:0] fifo_occupancy,fifo_high_water,roi_buffer_errors
);
 wire video_ready,roi_ready;
 assign s_ready=video_ready&&roi_ready;
 hci01_preprocess #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.BINS(64))u_video(
  .clk(clk),.rst_n(rst_n),.s_data(s_data),.s_valid(s_valid&&roi_ready),.s_sof(s_sof),.s_last(s_last),
  .cfg(hci_config),.s_ready(video_ready),.m_ready(m_ready),.m_data(m_data),.m_valid(m_valid),
  .m_sof(m_sof),.m_last(m_last),.m_eof(m_eof),.m_config(m_config),.errors(hci_errors),.frames(hci_frames),.lut_valid(hci_lut_valid));
 wire [2:0] rv,rs,rl,re,rready;
 wire [383:0] rgb;wire [95:0] gray;wire [8:0] rn;
 wire [47:0] rx,ry,rox,roy,rw,rh;wire [31:0] rfid,rseq;wire [63:0] rtime;wire [7:0] rflags;
 wire [31:0] roi_frames,invalid_frames,stale_frames,roi_errors;
 wire [191:0] active_windows;wire [2:0] active_enable;wire [15:0] active_ttl;
 hci02_roi_quad #(.WIDTH(WIDTH),.HEIGHT(HEIGHT))u_roi(
  .clk(clk),.rst_n(rst_n),.s_data(s_data),.s_valid(s_valid&&video_ready),.s_sof(s_sof),.s_last(s_last),.s_ready(roi_ready),
  .cfg_windows(roi_windows),.cfg_enable(roi_enable),.cfg_sequence(roi_sequence),.cfg_ttl(roi_ttl),.cfg_valid(roi_valid&&frame_tag_valid),
  .source_time_us(frame_time_us),.source_frame_id(frame_tag_id),.m_ready(rready),.m_valid(rv),.m_data(rgb),.m_gray(gray),.m_count(rn),
  .m_x(rx),.m_y(ry),.m_origin_x(rox),.m_origin_y(roy),.m_width(rw),.m_height(rh),.m_sof(rs),.m_last(rl),.m_eof(re),
  .m_frame_id(rfid),.m_config_sequence(rseq),.m_time_us(rtime),.m_flags(rflags),.frame_windows(active_windows),.frame_enable(active_enable),.frame_ttl(active_ttl),
  .frames(roi_frames),.invalid_frames(invalid_frames),.stale_frames(stale_frames),.errors(roi_errors));
 assign rready[2]=1'b1;
 assign crop_valid=rv&rready;assign crop_sof=rs;assign crop_last=rl;assign crop_eof=re;
 assign crop_rgb=rgb;assign crop_gray=gray;assign crop_count=rn;
 assign crop_x=rx;assign crop_y=ry;assign crop_origin_x=rox;assign crop_origin_y=roy;assign crop_width=rw;assign crop_height=rh;
 assign crop_frame_id=rfid;assign crop_sequence=rseq;assign crop_time_us=rtime;assign crop_flags=rflags;
 wire [95:0] crcs,roi_completed,roi_pixels,face_sums;wire [31:0] crc_errors;
 hci02_roi_crc_quad u_crc(.clk(clk),.rst_n(rst_n),.s_valid(rv&rready),.s_data(rgb),.s_gray(gray),.s_count(rn),.s_sof(rs),.s_eof(re),
  .s_width(rw),.s_height(rh),.last_crc(crcs),.completed_windows(roi_completed),.last_pixels(roi_pixels),.last_face_sum(face_sums),.errors(crc_errors));
 wire [1:0] eye_valid,eye_ready,result_valid;wire [242:0] eye_pixel[0:1];wire [767:0] eye_result[0:1];
 wire [31:0] eye_occupancy[0:1],eye_high_water[0:1],eye_fifo_errors[0:1];
 wire [31:0] ercv[0:1],ecmp[0:1],eskip[0:1],elabel[0:1],edead[0:1],eerror[0:1];
 genvar k;generate for(k=0;k<2;k=k+1)begin:eyes
  hci02_eye_pixel_fifo #(.DEPTH(EYE_FIFO_DEPTH))u_fifo(
   .clk(clk),.rst_n(rst_n),.s_valid(rv[k]),.s_ready(rready[k]),.s_gray(gray[k*32+:32]),.s_count(rn[k*3+:3]),
   .s_sof(rs[k]),.s_last(rl[k]),.s_eof(re[k]),.s_x(rx[k*16+:16]),.s_y(ry[k*16+:16]),
   .s_origin_x(rox[k*16+:16]),.s_origin_y(roy[k*16+:16]),.s_width(rw[k*16+:16]),.s_height(rh[k*16+:16]),
   .s_frame_id(rfid),.s_config_sequence(rseq),.s_time_us(rtime),.s_flags(rflags),
   .m_ready(eye_ready[k]),.m_valid(eye_valid[k]),.m_pixel(eye_pixel[k]),.occupancy(eye_occupancy[k]),.high_water(eye_high_water[k]),.errors(eye_fifo_errors[k]));
  hci02_eye_measure u_measure(.clk(clk),.rst_n(rst_n),.s_valid(eye_valid[k]),.s_gray(eye_pixel[k][7:0]),
   .s_sof(eye_pixel[k][8]),.s_last(eye_pixel[k][9]),.s_eof(eye_pixel[k][10]),.s_x(eye_pixel[k][26:11]),.s_y(eye_pixel[k][42:27]),
   .s_origin_x(eye_pixel[k][58:43]),.s_origin_y(eye_pixel[k][74:59]),.s_width(eye_pixel[k][90:75]),.s_height(eye_pixel[k][106:91]),
   .s_frame_id(eye_pixel[k][138:107]),.s_config_sequence(eye_pixel[k][170:139]),.s_time_us(eye_pixel[k][234:171]),.s_flags(eye_pixel[k][242:235]),
   .s_ready(eye_ready[k]),.m_ready(1'b1),.m_valid(result_valid[k]),.m_result(eye_result[k]),.received_windows(ercv[k]),.completed_windows(ecmp[k]),
   .skipped_windows(eskip[k]),.label_overflows(elabel[k]),.deadline_overflows(edead[k]),.errors(eerror[k]));
 end endgenerate
 assign feature_valid=result_valid;assign feature_result={eye_result[1],eye_result[0]};
 assign feature_received={ercv[1],ercv[0]};assign feature_skipped={eskip[1],eskip[0]};assign feature_deadline={edead[1],edead[0]};
 // Occupancy is the two-eye total; high-water is the worst single-eye RAM.
 assign fifo_occupancy=eye_occupancy[0]+eye_occupancy[1];
 assign fifo_high_water=eye_high_water[0]>eye_high_water[1]?eye_high_water[0]:eye_high_water[1];
 assign roi_buffer_errors=eye_fifo_errors[0]|eye_fifo_errors[1];
 wire lv=result_valid[0],ev=result_valid[1];wire [767:0] left_result=eye_result[0],right_result=eye_result[1];
 wire [31:0] lr=ercv[0],ls=eskip[0],ll=elabel[0],ld=edead[0],le=eerror[0];
 wire [31:0] er=ercv[1],es=eskip[1],el=elabel[1],ed=edead[1],ee=eerror[1];
 reg [767:0] stored_left,stored_right;reg [31:0] left_published,right_published;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin stored_left<=0;stored_right<=0;left_published<=0;right_published<=0;end
  else begin
   if(lv)begin stored_left<=left_result;left_published<=left_published+1'b1;end
   if(ev)begin stored_right<=right_result;right_published<=right_published+1'b1;end
  end
 end
 assign stats[767:0]=stored_left;
 assign stats[1535:768]=stored_right;
 assign stats[1695:1536]={ld,ll,ls,left_published,lr};
 assign stats[1855:1696]={ed,el,es,right_published,er};
 assign stats[1983:1856]={hci_errors|roi_errors|crc_errors|le|ee|roi_buffer_errors,stale_frames,invalid_frames,roi_frames};
 assign stats[2079:1984]=crcs;
 assign stats[2175:2080]=roi_completed;
 assign stats[2271:2176]=roi_pixels;
 assign stats[2303:2272]=rseq;
 assign stats[2335:2304]={13'd0,active_enable,active_ttl};
 assign stats[2527:2336]=active_windows;
 assign stats[2623:2528]=face_sums;
endmodule
