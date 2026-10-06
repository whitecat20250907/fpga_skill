`timescale 1ns/1ps
module tb_isp_interfaces;
    reg clk=0;always #4 clk=~clk;
    reg rst=0,iv=0,il=0,iu=0,orr=1;
    reg [39:0] idata=0;
    wire ir,ov,ol,ou;wire [39:0] od;wire [9:0] dest;
    integer cy,cx,seen=0,f,y,x,holes,cycles=0;
    reg [39:0] held;reg hl,hu,stalled=0;
    image_correction crop(.I_clk(clk),.I_rst_n(rst),
        .I_v_start(15'd1),.I_v_end(15'd5),.I_h_end(15'd5),
        .I_raw_tdata(idata),.I_raw_tdest(10'd17),.I_raw_tlast(il),
        .I_raw_tvalid(iv),.I_raw_tuser(iu),.I_raw_tready(ir),
        .O_raw_tdata(od),.O_raw_tlast(ol),.O_raw_tdest(dest),
        .O_raw_tvalid(ov),.O_raw_tuser(ou),.O_raw_tready(orr));
    reg lv=0,lu=0;reg [32:0] ld=0;
    wire lov;wire [32:0] lod;
    ui_line_buffer_demosaic lb(.I_clk(clk),.I_rst_n(rst),.I_img_width(13'd16),
        .I_tuser(lu),.I_valid(lv),.I_data(ld),.O_valid(lov),.O_data(lod));
    integer lexpect=0,lseen=0,lframe=0,ly=0,lx=0;
    reg lsending=0;
    reg [32:0] lqueue[0:99];integer qhead=0,qtail=0;
    reg completed=0;
    always @(negedge clk) begin cycles=cycles+1;orr=(cycles%7!=0)&&(cycles%7!=1);end
    always @(posedge clk) if(rst) begin
        if(stalled&&(od!==held||ol!==hl||ou!==hu||!ov)) $fatal(1,"crop stalled output");
        stalled=ov&&!orr;held=od;hl=ol;hu=ou;
        if(ov&&orr) begin
            cy=(seen%12)/4+2;cx=seen%4+1;
            if(od!==(seen/12)*10000+cy*100+cx||dest!==17||ol!==(cx==4)||ou!==((seen%12)==0))
                $fatal(1,"crop index%0d got%0d y%0d x%0d SOF%0b EOL%0b",seen,od,cy,cx,ou,ol);
            seen=seen+1;
        end
        if(lov) begin
            if(qhead==qtail) $fatal(1,"line output without predecessor");
            if(lod!==lqueue[qhead]) $fatal(1,"linebuffer %0d got%0d expected%0d",qhead,lod,lqueue[qhead]);
            qhead=qhead+1;lseen=lseen+1;
        end
    end
    initial begin
        repeat(5) @(posedge clk);@(negedge clk);rst=1;
        for(f=0;f<3;f=f+1) begin
            // Invalid TLAST must never move the crop's line counter.
            @(negedge clk);iv=0;il=1;iu=1;@(posedge clk);
            for(y=0;y<6;y=y+1) for(x=0;x<6;x=x+1) begin
                repeat((x+y+f)%3) begin @(negedge clk);iv=0;il=1;iu=0;@(posedge clk);end
                @(negedge clk);iv=1;il=(x==5);iu=0;idata=f*10000+y*100+x;
                @(posedge clk);while(!ir) @(posedge clk);
            end
            @(negedge clk);iv=0;il=0;iu=0;
        end
        wait(seen==36);
        // Line-buffer predecessor test over frames and valid holes. SOF is
        // deliberately adjacent to the previous frame's final write.
        for(f=0;f<3;f=f+1) for(y=0;y<4;y=y+1) for(x=0;x<4;x=x+1) begin
            repeat((x+y+f)%3) begin @(negedge clk);lv=0;lu=0;@(posedge clk);end
            @(negedge clk);lv=1;lu=(x==0&&y==0);ld=f*10000+y*100+x;
            if(y>0) begin lqueue[qtail]=f*10000+(y-1)*100+x;qtail=qtail+1;end
            @(posedge clk);
        end
        @(negedge clk);lv=0;lu=0;
        repeat(8) @(posedge clk);
        if(seen!=36||lseen!=36) $fatal(1,"counts crop%0d line%0d",seen,lseen);
        completed=1;$display("PASS crop invalid-TLAST/SOF holes/stall 36 beats; line predecessor 36 beats");$finish;
    end
    initial begin #1000000;$fatal(1,"interface timeout");end
endmodule
