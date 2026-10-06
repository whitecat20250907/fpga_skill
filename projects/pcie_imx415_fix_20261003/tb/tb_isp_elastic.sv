`timescale 1ns/1ps
module tb_isp_elastic;
    reg clk=0;always #4 clk=~clk;
    reg rst=0,iv=0,il=0,iu=0,ready=1;
    reg [95:0] id=0;
    wire ir;
    wire [95:0] d[0:4];wire [4:0] v,l,u,r;
    reg [11:0] lut[0:255];
    reg [95:0] expectq[0:2047];reg lastq[0:2047],userq[0:2047];
    integer head=0,tail=0,n,f,y,x,p,c,cycles=0;
    reg [95:0] held;reg hl,hu,stalled=0;
    reg completed=0;
    ui_image_cut #(.DATA_WIDTH(96),.SKIP_ROWS_top(0),.SKIP_ROWS_bottom(0),.SKIP_COLS_left(1),.SKIP_COLS_right(0)) cut(
        .I_clk(clk),.I_rst_n(rst),.I_img_width(13'd64),.I_img_height(13'd8),
        .I_tdata(id),.I_tvalid(iv),.I_tlast(il),.I_tuser(iu),.I_tready(ir),
        .O_tdata(d[0]),.O_tvalid(v[0]),.O_tlast(l[0]),.O_tuser(u[0]),.O_tready(r[0]));
    ui_gamma #(.GAMMA_10x(22)) gamma(.I_clk(clk),.I_rst_n(rst),
        .I_tdata(d[0]),.I_tvalid(v[0]),.I_tlast(l[0]),.I_tuser(u[0]),.I_tready(r[0]),
        .O_tdata(d[1]),.O_tvalid(v[1]),.O_tlast(l[1]),.O_tuser(u[1]),.O_tready(r[1]));
    ui_Contrast_adj #(.contrast_level(140)) contrast(.I_clk(clk),.I_rst_n(rst),
        .I_tdata(d[1]),.I_tvalid(v[1]),.I_tlast(l[1]),.I_tuser(u[1]),.I_tready(r[1]),
        .O_tdata(d[2]),.O_tvalid(v[2]),.O_tlast(l[2]),.O_tuser(u[2]),.O_tready(r[2]));
    ui_Brightness_adj #(.BRIGHTNESS_ADD(5),.BRIGHTNESS_MINUS(0)) brightness(.I_clk(clk),.I_rst_n(rst),
        .I_tdata(d[2]),.I_tvalid(v[2]),.I_tlast(l[2]),.I_tuser(u[2]),.I_tready(r[2]),
        .O_tdata(d[3]),.O_tvalid(v[3]),.O_tlast(l[3]),.O_tuser(u[3]),.O_tready(r[3]));
    ui_Saturation_adj #(.ADJUST_VAL(130)) saturation(.I_clk(clk),.I_rst_n(rst),
        .I_tdata(d[3]),.I_tvalid(v[3]),.I_tlast(l[3]),.I_tuser(u[3]),.I_tready(r[3]),
        .O_tdata(d[4]),.O_tvalid(v[4]),.O_tlast(l[4]),.O_tuser(u[4]),.O_tready(ready));
    function integer clamp(input integer val);
        clamp=(val<0)?0:((val>255)?255:val);
    endfunction
    function integer adjust(input integer val);
        integer z;
        begin z=(lut[val]*256-2048)>>12; z=clamp(((z-128)*140)>>>7)+128;
            // Clamp contrast after adding 128, then apply brightness.
            z=(lut[val]*256-2048)>>12;
            adjust=clamp(clamp((((z-128)*140)>>>7)+128)+5);
        end
    endfunction
    function [23:0] golden(input [23:0] pixel);
        integer rr,gg,bb,yy;
        begin
            rr=adjust(pixel[23:16]);gg=adjust(pixel[15:8]);bb=adjust(pixel[7:0]);
            yy=(rr*306+gg*601+bb*117)>>10;
            golden={8'(clamp((rr*385-yy*130)>>>8)),8'(clamp((gg*385-yy*130)>>>8)),8'(clamp((bb*385-yy*130)>>>8))};
        end
    endfunction
    always @(negedge clk) begin cycles=cycles+1;ready=(cycles%127<95)&&(cycles%11!=0);end
    always @(posedge clk) if(rst) begin
        if(iv&&ir) begin
            for(p=0;p<4;p=p+1) expectq[tail][24*p+:24]=golden((tail%16==0)?24'd0:id[24*p+:24]);
            lastq[tail]=il;userq[tail]=iu;tail=tail+1;
        end
        if(stalled&&(d[4]!==held||l[4]!==hl||u[4]!==hu||!v[4])) $fatal(1,"backend stalled output");
        stalled=v[4]&&!ready;held=d[4];hl=l[4];hu=u[4];
        if(v[4]&&ready) begin
            if(head==tail) $fatal(1,"backend extra beat");
            if(d[4]!==expectq[head]||l[4]!==lastq[head]||u[4]!==userq[head])
                $fatal(1,"backend index%0d got%024x expected%024x L%0b U%0b",head,d[4],expectq[head],l[4],u[4]);
            head=head+1;
        end
    end
    reg biv=0,bil=0,biu=0,br=1;reg [39:0] bd=0;reg [9:0] bdest=0;
    wire bir,bov,bol,bou;wire [39:0] bod;wire [9:0] bodest;
    reg [39:0] bexpect[0:1023];reg [9:0] bdestq[0:1023];reg blq[0:1023],buq[0:1023];
    integer bh=0,bt=0,bn,k,level;reg [39:0] bhold;reg [9:0] bdh;reg blh,buh,bsv=0;
    ui_BLC #(.Black_level_offset_r0(5),.Black_level_offset_r1(50),.Black_level_offset_r2(100),.Black_level_offset_r3(1023)) blc(
        .I_clk(clk),.I_rst_n(rst),.I_tdata(bd),.I_tvalid(biv),.I_tlast(bil),.I_tuser(biu),.I_tdest(bdest),.I_tready(bir),
        .O_tdata(bod),.O_tvalid(bov),.O_tlast(bol),.O_tuser(bou),.O_tdest(bodest),.O_tready(br));
    always @(negedge clk) br=(cycles%23<17);
    always @(posedge clk) if(rst) begin
        if(biv&&bir) begin
            for(k=0;k<4;k=k+1) begin
                level=(k==0)?5:((k==1)?50:((k==2)?100:1023));
                bexpect[bt][10*k+:10]=(bd[10*k+:10]>level)?bd[10*k+:10]-level:0;
            end
            bdestq[bt]=bdest;blq[bt]=bil;buq[bt]=biu;bt=bt+1;
        end
        if(bsv&&(bod!==bhold||bodest!==bdh||bol!==blh||bou!==buh||!bov)) $fatal(1,"BLC stalled output");
        bsv=bov&&!br;bhold=bod;bdh=bodest;blh=bol;buh=bou;
        if(bov&&br) begin
            if(bod!==bexpect[bh]||bodest!==bdestq[bh]||bol!==blq[bh]||bou!==buq[bh]) $fatal(1,"BLC index%0d",bh);
            bh=bh+1;
        end
    end
    reg backend_done=0,blc_done=0;
    initial begin
        $readmemh("gamma22.hex",lut);
        repeat(5) @(posedge clk);@(negedge clk);rst=1;
        for(f=0;f<10;f=f+1) for(y=0;y<8;y=y+1) for(x=0;x<16;x=x+1) begin
            repeat((x+y+f)%3) begin @(negedge clk);iv=0;il=0;iu=0;@(posedge clk);end
            @(negedge clk);iv=1;il=(x==15);iu=(x==0&&y==0);
            for(n=0;n<12;n=n+1) id[8*n+:8]=(f*41+y*17+x*13+n*31)%256;
            @(posedge clk);while(!ir) @(posedge clk);
        end
        @(negedge clk);iv=0;il=0;iu=0;wait(head==1280);backend_done=1;
    end
    initial begin
        wait(rst);
        for(bn=0;bn<1000;bn=bn+1) begin
            repeat(bn%3) begin @(negedge clk);biv=0;bil=0;biu=0;@(posedge clk);end
            @(negedge clk);biv=1;bil=(bn%8==7);biu=(bn%40==0);bdest=bn%1024;
            for(n=0;n<4;n=n+1) bd[10*n+:10]=(bn*31+n*137)%1024;
            @(posedge clk);while(!bir) @(posedge clk);
        end
        @(negedge clk);biv=0;wait(bh==1000);blc_done=1;
    end
    initial begin wait(backend_done&&blc_done);completed=1;$display("PASS elastic backend 1280 beats/10 frames, BLC 1000 beats, holes/32-cycle stalls");$finish;end
    initial begin #1000000;$fatal(1,"elastic timeout");end
endmodule
