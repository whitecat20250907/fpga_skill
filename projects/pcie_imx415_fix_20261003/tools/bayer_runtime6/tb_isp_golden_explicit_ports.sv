`timescale 1ns/1ps
module isp_case #(parameter MODE="RGGB", parameter ID=0)(output reg done=0);
    reg clk=0; always #4 clk=~clk;
    reg reset_n=0;
    reg [12:0] width=16, height=6;
    reg [39:0] data=0;
    reg valid=0,last=0,user=0,ready=1;
    wire inready,ovalid,olast,ouser;
    wire [127:0] rgb;
    wire [39:0] blc_data;
    wire blc_valid,blc_last,blc_user,matrix_ready;
    integer frame_index=0, expected_index=0, output_frames=0;
    integer w=16,h=6,tx,ty,f, p,n, expectpixel,seen=0,errors=0;
    integer cycles=0,stall_pattern=0;
    reg [127:0] held_rgb;
    reg held_last,held_user,stalled=0;
`ifndef BASELINE_TEST
    ui_BLC #(.Black_level_offset_r0(0),.Black_level_offset_r1(0),.Black_level_offset_r2(0),.Black_level_offset_r3(0)) input_blc(
        .I_clk(clk),.I_rst_n(reset_n),.I_tdata(data),.I_tdest(10'd0),
        .I_tvalid(valid),.I_tlast(last),.I_tuser(user),.I_tready(inready),
        .O_tdata(blc_data),.O_tdest(),.O_tvalid(blc_valid),.O_tlast(blc_last),.O_tuser(blc_user),.O_tready(matrix_ready));
`else
    assign blc_data=data;assign blc_valid=valid;assign blc_last=last;assign blc_user=user;
    assign inready=matrix_ready;
`endif
    ui_top_demosaic #(.BAYER_MODE(MODE)) dut(
        .I_clk(clk),.I_rst_n(reset_n),.I_bayer_mode((MODE=="RGGB")?2'd0:(MODE=="BGGR")?2'd1:(MODE=="GRBG")?2'd2:2'd3),.I_img_width(width),.I_img_height(height),
        .I_axi4s_tdata(blc_data),.I_axi4s_tdest(10'd0),.I_axi4s_tlast(blc_last),
        .I_axi4s_tvalid(blc_valid),.I_axi4s_tuser(blc_user),.I_axi4s_tready(matrix_ready),
        .O_tdata(rgb),.O_tvalid(ovalid),.O_tlast(olast),.O_tuser(ouser),.O_tready(ready));
    function integer site(input integer y,x);
        if(MODE=="RGGB") site=(!(y%2)&&!(x%2))?0:((y%2&&x%2)?2:1);
        else if(MODE=="BGGR") site=(!(y%2)&&!(x%2))?2:((y%2&&x%2)?0:1);
        else if(MODE=="GRBG") site=(!(y%2)&&(x%2))?0:((y%2&&!(x%2))?2:1);
        else site=(!(y%2)&&(x%2))?2:((y%2&&!(x%2))?0:1);
    endfunction
    function integer mirror(input integer a,size);
        if(size==1) mirror=0;
        else if(a<0) mirror=-a;
        else if(a>=size) mirror=2*size-2-a;
        else mirror=a;
    endfunction
    function integer raw(input integer frame,y,x);
        integer cy,cx,c;
        begin
            cy=mirror(y,h); cx=mirror(x,w); c=site(cy,cx);
            raw=(23+c*61+cy*7+cx*5+frame*11)%256;
        end
    endfunction
    function integer channel(input integer frame,y,x,c);
        integer s,neighbor;
        begin
            s=site(y,x);
            if(s==c) channel=raw(frame,y,x);
            else if(s==1) begin
                neighbor=site(y,x^1);
                if(neighbor==c) channel=(raw(frame,y,x-1)+raw(frame,y,x+1))/2;
                else channel=(raw(frame,y-1,x)+raw(frame,y+1,x))/2;
            end else if(c==1)
                channel=(raw(frame,y-1,x)+raw(frame,y+1,x)+raw(frame,y,x-1)+raw(frame,y,x+1))/4;
            else
                channel=(raw(frame,y-1,x-1)+raw(frame,y-1,x+1)+raw(frame,y+1,x-1)+raw(frame,y+1,x+1))/4;
        end
    endfunction
    task sendbeat(input integer frame,y,x,input integer holes);
        integer k;
        reg [39:0] word;
        begin
            word=0;
            for(k=0;k<4;k=k+1) word[10*k +:10]=raw(frame,y,x+k)*4;
            repeat(holes) begin
                @(negedge clk);valid=0;user=0;last=0;
                @(posedge clk);
            end
            @(negedge clk); data=word;valid=1;user=(x==0&&y==0);last=(x==w-4);
            @(posedge clk); while(!inready) @(posedge clk);
        end
    endtask
    always @(negedge clk) begin
        cycles=cycles+1;
        ready=(stall_pattern==0)||((cycles%17!=0)&&(cycles%17!=1)&&(cycles%29!=0));
    end
    always @(posedge clk) if(reset_n) begin
        if(stalled && (rgb!==held_rgb||olast!==held_last||ouser!==held_user||!ovalid))
            $fatal(1,"%s changed stalled output",MODE);
        stalled=ovalid&&!ready;held_rgb=rgb;held_last=olast;held_user=ouser;
        if(ovalid&&ready) begin
            if(ouser!==(expected_index==0)) $fatal(1,"%s SOF index %0d",MODE,expected_index);
            if(olast!==((expected_index%(w/4))==w/4-1)) $fatal(1,"%s EOL index %0d",MODE,expected_index);
            for(p=0;p<4;p=p+1) begin
                tx=(expected_index%(w/4))*4+p;ty=expected_index/(w/4);
                expectpixel=(channel(frame_index,ty,tx,0)<<16)|(channel(frame_index,ty,tx,1)<<8)|channel(frame_index,ty,tx,2);
                if(rgb[32*p +:32]!==expectpixel)
                    $fatal(1,"%s frame%0d x%0d y%0d got%08x expected%08x",MODE,frame_index,tx,ty,rgb[32*p +:32],expectpixel);
            end
            expected_index=expected_index+1; seen=seen+1;
            if(expected_index==w*h/4) begin
                expected_index=0;frame_index=frame_index+1;output_frames=output_frames+1;
            end
        end
    end
    integer base_frame;
    task runshape(input integer sw,sh,frames,holes,stalls);
        integer ii,jj,ff;
        begin
            w=sw;h=sh;width=sw;height=sh;stall_pattern=stalls;
            base_frame=frame_index;
            for(ff=0;ff<frames;ff=ff+1) begin
                for(jj=0;jj<sh;jj=jj+1)
                    for(ii=0;ii<sw;ii=ii+4)
                        sendbeat(base_frame+ff,jj,ii,holes?((ii/4+jj+ff)%4):0);
                @(negedge clk);valid=0;user=0;last=0;
            end
            wait(frame_index==base_frame+frames);
            repeat(8) @(posedge clk);
            $display("PASS %s %0dx%0d frames=%0d holes=%0d stalls=%0d",MODE,sw,sh,frames,holes,stalls);
        end
    endtask
    initial begin
        repeat(5) @(posedge clk);@(negedge clk);reset_n=1;
`ifdef BASELINE_TEST
        runshape(16,6,1,1,0);
`else
        runshape(4,1,3,0,0);
        runshape(8,2,3,1,1);
        runshape(16,6,4,0,1);
        runshape(20,7,3,1,1);
        runshape(1280,720,2,1,1);
        runshape(1920,1080,2,1,1);
`endif
        done=1;
    end
    initial begin #100000000;$fatal(1,"%s timeout",MODE);end
endmodule
module tb_isp_golden;
    wire [3:0] done;
    isp_case #(.MODE("RGGB"),.ID(0)) rg(done[0]);
    isp_case #(.MODE("BGGR"),.ID(1)) bg(done[1]);
    isp_case #(.MODE("GRBG"),.ID(2)) gr(done[2]);
    isp_case #(.MODE("GBRG"),.ID(3)) gb(done[3]);
    initial begin wait(&done);$display("PASS ISP ALL GOLDEN CASES");$finish;end
endmodule
