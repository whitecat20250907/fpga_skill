`timescale 1ns/1ps
module tb_isp_parameters;
    reg clk=0;always #4 clk=~clk;
    reg rst=0,valid=0,last=0,user=0,ready=1;reg [95:0] data=0;
    wire [5:0] ir,ov,ol,ou;wire [95:0] od[0:5];
    reg [11:0] gamma[0:255];
    reg [95:0] expected[0:5][0:767];reg lq[0:767],uq[0:767];
    integer head[0:5],tail=0,cycles=0,n,p,j,z,k,coef;
    reg [95:0] held[0:5];reg [5:0] stalled=0,hl=0,hu=0;
    reg completed=0;
    ui_gamma #(.GAMMA_10x(8)) gamma08(.I_clk(clk),.I_rst_n(rst),.I_tdata(data),.I_tvalid(valid),
        .I_tlast(last),.I_tuser(user),.I_tready(ir[0]),.O_tdata(od[0]),.O_tvalid(ov[0]),.O_tlast(ol[0]),.O_tuser(ou[0]),.O_tready(ready));
    genvar g;
    generate for(g=1;g<6;g=g+1) begin: contrast
        localparam LEVEL=(g==1)?1:((g==2)?3:((g==3)?139:((g==4)?140:255)));
        ui_Contrast_adj #(.contrast_level(LEVEL)) dut(.I_clk(clk),.I_rst_n(rst),.I_tdata(data),.I_tvalid(valid),
            .I_tlast(last),.I_tuser(user),.I_tready(ir[g]),.O_tdata(od[g]),.O_tvalid(ov[g]),.O_tlast(ol[g]),.O_tuser(ou[g]),.O_tready(ready));
    end endgenerate
    always @(negedge clk) begin cycles=cycles+1;ready=(cycles%71<51)&&(cycles%11!=0);end
    always @(posedge clk) if(rst) begin
        if(valid&&(&ir)) begin
            for(j=0;j<6;j=j+1) for(p=0;p<12;p=p+1) begin
                z=data[8*p+:8];
                if(j==0) begin z=gamma[z];z=(z*256-2048)>>>12;end
                else begin
                    coef=(j==1)?1:((j==2)?3:((j==3)?139:((j==4)?140:255)));
                    z=(((z-128)*coef)>>>7)+128;
                end
                expected[j][tail][8*p+:8]=(z<0)?0:((z>255)?255:z);
            end
            lq[tail]=last;uq[tail]=user;tail=tail+1;
        end
        for(j=0;j<6;j=j+1) begin
            if(stalled[j]&&(od[j]!==held[j]||ol[j]!==hl[j]||ou[j]!==hu[j]||!ov[j])) $fatal(1,"parameter stalled %0d",j);
            stalled[j]=ov[j]&&!ready;held[j]=od[j];hl[j]=ol[j];hu[j]=ou[j];
            if(ov[j]&&ready) begin
                if(od[j]!==expected[j][head[j]]||ol[j]!==lq[head[j]]||ou[j]!==uq[head[j]])
                    $fatal(1,"parameter%0d idx%0d got%024x expected%024x",j,head[j],od[j],expected[j][head[j]]);
                head[j]=head[j]+1;
            end
        end
    end
    initial begin
        $readmemh("gamma08.hex",gamma);
        for(k=0;k<6;k=k+1) head[k]=0;
        repeat(5) @(posedge clk);@(negedge clk);rst=1;
        // All stages receive a beat only when all elastic inputs accept it.
        // Deliberate bubbles keep their different pipeline depths drained.
        for(n=0;n<768;n=n+1) begin
            @(negedge clk);valid=0;last=0;user=0;
            repeat(35) @(posedge clk);
            @(negedge clk);valid=1;last=(n%16==15);user=(n%128==0);
            for(p=0;p<12;p=p+1) data[8*p+:8]=(n+p*23)%256;
            @(posedge clk);while(!(&ir)) @(posedge clk);
        end
        @(negedge clk);valid=0;
        wait(head[0]==768&&head[1]==768&&head[2]==768&&head[3]==768&&head[4]==768&&head[5]==768);
        completed=1;$display("PASS gamma0.8 all256 inputs; signed contrast levels1/3/139/140/255 all256, markers/stalls");$finish;
    end
    initial begin #1000000;$fatal(1,"parameter timeout");end
endmodule
