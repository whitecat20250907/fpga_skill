`timescale 1ns/1ps
module tb_lz1_lane_engine_480;
    localparam N=480, CASES=4;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0,cap_valid=0,cap_line_start=0,cap_bank=0;
    reg [7:0] cap_gray=0;
    reg [8:0] cap_addr=0,read_addr=0;
    reg start=0,start_bank=0,read_bank=0,read_mode=0;
    wire busy,done,done_bank,done_mode;
    wire [8:0] done_length;
    wire [7:0] read_data;
    reg [7:0] inputs[0:CASES*N-1],expected[0:CASES*N-1];
    reg [15:0] params[0:CASES-1];
    integer c,i,cycles;
    lz1_lane_engine #(.N(N)) dut (
        .clk(clk),.rst_n(rst_n),.cap_valid(cap_valid),
        .cap_gray(cap_gray),.cap_addr(cap_addr),
        .cap_line_start(cap_line_start),.cap_bank(cap_bank),
        .start(start),.start_bank(start_bank),.busy(busy),
        .done(done),.done_bank(done_bank),.done_mode(done_mode),
        .done_length(done_length),.read_bank(read_bank),
        .read_mode(read_mode),.read_addr(read_addr),.read_data(read_data)
    );
    initial begin
        $readmemh("tb/generated/lz1_input_480.hex",inputs);
        $readmemh("tb/generated/lz1_expected_480.hex",expected);
        $readmemh("tb/generated/lz1_params_480.hex",params);
        repeat (4) @(posedge clk);
        @(negedge clk);rst_n=1;
        for (c=0;c<CASES;c=c+1) begin
            for (i=0;i<N;i=i+1) begin
                @(negedge clk);
                cap_valid=1;cap_addr=i;cap_gray=inputs[c*N+i];
                cap_line_start=(i==0);
                @(posedge clk);
            end
            @(negedge clk);cap_valid=0;cap_line_start=0;start=1;
            @(negedge clk);start=0;
            cycles=0;
            while (!done && cycles<2*N+10) begin
                @(posedge clk);#1;cycles=cycles+1;
            end
            if (!done) $fatal(1,"encoder timed out on case %0d",c);
            if (done_bank!==0 || done_mode!==params[c][9] ||
                done_length!==params[c][8:0])
                $fatal(1,"case %0d mode=%b len=%0d expected=%h",
                       c,done_mode,done_length,params[c]);
            read_mode=done_mode;
            for (i=0;i<done_length;i=i+1) begin
                read_addr=i;#1;
                if (read_data!==expected[c*N+i])
                    $fatal(1,"case %0d byte %0d got=%h expected=%h",
                           c,i,read_data,expected[c*N+i]);
            end
            @(negedge clk);
        end
        $display("PASS LZ77 lane: four 480-byte Python golden vectors");
        $finish;
    end
endmodule
