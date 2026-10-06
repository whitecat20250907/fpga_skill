`timescale 1ns/1ps
module tb_pack4;
 reg clk=0; always #4 clk=~clk;
 reg rst_n=0,enable=0,s_tvalid=0,s_tlast=0,s_tuser=0,m_tready=0;
 reg [127:0] s_tdata=0;
 reg [12:0] cfg_img_height=1;
 wire s_tready,m_tvalid,m_tlast,m_frame_last,sof,eof;
 wire [127:0] m_tdata;
 wire [31:0] frame_count_out;
 pack4_rgb24_to_128 dut(.*);
 integer width_now=4,height_now=1,words_line=1,out_word=0;
 integer cycles=0,fails=0,sofs=0,eofs=0;
 reg prior_stall=0;
 reg [131:0] held;
 function automatic [7:0] value(input integer pixel,input integer channel);
  value=(pixel*7+channel*67+19)%256;
 endfunction
 always @(negedge clk) begin
  cycles=cycles+1;
  m_tready=(cycles%23>=7 && cycles%7!=0);
 end
 always @(posedge clk) if (rst_n && enable) begin : check
  integer f,y,word_x,b,byte_x,pixel,channel;
  reg [127:0] expected;
  if (prior_stall && {m_tdata,m_tlast,m_frame_last,sof,eof} !== held)
   $fatal(1,"Output changed under backpressure");
  prior_stall=m_tvalid&&!m_tready;
  held={m_tdata,m_tlast,m_frame_last,sof,eof};
  if (m_tvalid && m_tready) begin
   f=out_word/(words_line*height_now);
   y=(out_word/words_line)%height_now;
   word_x=out_word%words_line;
   expected=0;
   for(b=0;b<16;b=b+1) begin
    byte_x=word_x*16+b;
    if(byte_x<width_now*3) begin
     pixel=(f*height_now+y)*width_now+byte_x/3;
     channel=byte_x%3;
     expected[b*8+:8]=value(pixel,channel);
    end
   end
   if(m_tdata!==expected) $fatal(1,"RGB data mismatch word=%0d got=%h expected=%h",out_word,m_tdata,expected);
   if(m_tlast !== (word_x==words_line-1)) $fatal(1,"EOL wrong at word %0d",out_word);
   if(m_frame_last !== (y==height_now-1 && word_x==words_line-1)) $fatal(1,"EOF wrong at word %0d",out_word);
   if(eof!==m_frame_last) $fatal(1,"EOF sideband mismatch");
   if(sof !== (y==0 && word_x==0)) $fatal(1,"SOF wrong at word %0d",out_word);
   if(sof) sofs=sofs+1;
   if(eof) eofs=eofs+1;
   out_word=out_word+1;
  end
 end else prior_stall=0;
 task automatic run_case(input integer w,input integer h,input integer frames);
  integer f,y,x,k,pixel,expected_words,wait_cycles;
  begin
   @(negedge clk);rst_n=0;enable=0;s_tvalid=0;
   repeat(4) @(negedge clk);
   width_now=w;height_now=h;cfg_img_height=h;words_line=(w*3+15)/16;
   out_word=0;sofs=0;eofs=0;rst_n=1;enable=1;
   for(f=0;f<frames;f=f+1) for(y=0;y<h;y=y+1) for(x=0;x<w;x=x+4) begin
    @(negedge clk);
    s_tdata=0;
    for(k=0;k<4;k=k+1) begin
     pixel=(f*h+y)*w+x+k;
     s_tdata[k*32+:32]={8'd0,value(pixel,0),value(pixel,1),value(pixel,2)};
    end
    s_tlast=(x==w-4);s_tuser=(y==0&&x==0);s_tvalid=1;
    do @(posedge clk); while(!s_tready);
    @(negedge clk);s_tvalid=0;s_tuser=0;s_tlast=0;
    if(x==w-4) repeat(3) @(negedge clk);
   end
   expected_words=words_line*h*frames;wait_cycles=0;
   while(out_word<expected_words && wait_cycles<5000) begin
    @(negedge clk);wait_cycles=wait_cycles+1;
   end
   repeat(15) @(negedge clk);
   if(out_word!=expected_words || sofs!=frames || eofs!=frames || frame_count_out!=frames)
    $fatal(1,"Frame counts wrong w=%0d h=%0d words=%0d/%0d sof=%0d eof=%0d count=%0d",w,h,out_word,expected_words,sofs,eofs,frame_count_out);
   $display("PASS pack4 %0dx%0d frames=%0d words=%0d",w,h,frames,out_word);
  end
 endtask
 initial begin
  run_case(4,1,2);run_case(8,3,3);run_case(12,2,2);
  run_case(16,3,3);run_case(20,3,2);
  run_case(1280,720,2);run_case(1920,1080,2);
  $display("ALL_PACK4_TESTS_PASS");$finish;
 end
 initial begin #50000000; $fatal(1,"Timeout");end
endmodule
