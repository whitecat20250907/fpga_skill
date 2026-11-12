// Four RGB3 pixels per accepted source beat; one/two area3 pixels per result.
// Pixel0 is the low 24 bits; each pixel has R low, G middle, B high byte.
// WIDTH must be divisible by 12, HEIGHT by 3. Defaults match 1080p RGB3.
// Results are provisional until a complete accepted EOF; never commit prefixes.
`timescale 1ns/1ps
`default_nettype none
module rgb_area3_4ppc #(
    parameter WIDTH=1920, HEIGHT=1080
)(
    input wire clk,rst_n,
    input wire in_valid,
    output wire in_ready,
    input wire [95:0] in_rgb,
    input wire in_sof,in_eol,
    input wire [31:0] in_frame_id,
    input wire [63:0] in_source_ns,
    output reg out_valid,
    input wire out_ready,
    output reg [47:0] out_rgb,
    output reg [1:0] out_count,
    output reg out_sof,out_eol,out_eof,
    output reg [31:0] out_frame_id,
    output reg [63:0] out_source_ns,
    output reg [31:0] frame_starts,frame_completions,frame_aborts,
    output reg framing_error
);
    localparam COLS=WIDTH/3;
    localparam BANK_WORDS=COLS/2;
    (* ram_style="bram(min_area)" *) reg [32:0] even_columns[0:BANK_WORDS-1];
    (* ram_style="bram(min_area)" *) reg [32:0] odd_columns[0:BANK_WORDS-1];
    reg [32:0] even_read,odd_read;
    reg active;
    reg [15:0] x,y,column;
    reg [1:0] phase,vertical;
    reg [29:0] horizontal;
    reg [31:0] source_id;
    reg [63:0] source_ns;
    reg pending,p_first_odd,p_two,p_sof,p_eol,p_eof;
    reg [1:0] p_vertical;
    reg [15:0] p_even_address,p_odd_address;
    reg [32:0] p_even_sum,p_odd_sum;
    reg [31:0] p_id;
    reg [63:0] p_ns;
    wire advance=!out_valid || out_ready;
    assign in_ready=advance;
    wire accept=in_valid && in_ready;
    wire framed=in_sof || active;
    wire [15:0] wx=in_sof ? 16'd0:x;
    wire [15:0] wy=in_sof ? 16'd0:y;
    wire [15:0] wc=in_sof ? 16'd0:column;
    wire [1:0] hp=in_sof ? 2'd0:phase;
    wire [1:0] vp=in_sof ? 2'd0:vertical;
    wire legal_eol=(in_eol==(wx==WIDTH-4));
    wire two=(hp==2);
    wire [15:0] even_address=(two && wc[0]) ? ((wc+16'd1)>>1):(wc>>1);
    wire [15:0] odd_address=wc>>1;
    reg [32:0] sum0,sum1;
    reg [29:0] next_horizontal;
    integer channel;
    reg [9:0] a,b,c,d,carry;
    always @* begin
        sum0=0;sum1=0;next_horizontal=0;
        a=0;b=0;c=0;d=0;carry=0;
        for(channel=0;channel<3;channel=channel+1) begin
            a={2'b0,in_rgb[channel*8+:8]};
            b={2'b0,in_rgb[24+channel*8+:8]};
            c={2'b0,in_rgb[48+channel*8+:8]};
            d={2'b0,in_rgb[72+channel*8+:8]};
            carry=horizontal[channel*10+:10];
            case(hp)
                0: begin
                    sum0[channel*11+:11]={1'b0,a}+{1'b0,b}+{1'b0,c};
                    next_horizontal[channel*10+:10]=d;
                end
                1: begin
                    sum0[channel*11+:11]={1'b0,carry}+{1'b0,a}+{1'b0,b};
                    next_horizontal[channel*10+:10]=c+d;
                end
                default: begin
                    sum0[channel*11+:11]={1'b0,carry}+{1'b0,a};
                    sum1[channel*11+:11]={1'b0,b}+{1'b0,c}+{1'b0,d};
                end
            endcase
        end
    end
    function [32:0] add_channels;
        input [32:0] left,right;
        integer ch;
        begin
            for(ch=0;ch<3;ch=ch+1)
                add_channels[ch*11+:11]=left[ch*11+:11]+right[ch*11+:11];
        end
    endfunction
    function [23:0] mean_channels;
        input [32:0] previous,row_sum;
        integer ch;
        reg [11:0] total;
        begin
            total=0;
            for(ch=0;ch<3;ch=ch+1) begin
                total={1'b0,previous[ch*11+:11]}+{1'b0,row_sum[ch*11+:11]}+12'd4;
                mean_channels[ch*8+:8]=total/12'd9;
            end
        end
    endfunction
    wire [23:0] even_mean=mean_channels(even_read,p_even_sum);
    wire [23:0] odd_mean=mean_channels(odd_read,p_odd_sum);

    // Both banks have synchronous reads. One queued beat supplies the write
    // addresses/data; no array reset. Row0 overwrites before row1 reads.
    always @(posedge clk) begin
        if(rst_n && advance) begin
            if(accept && framed && legal_eol) begin
                even_read<=even_columns[even_address];
                odd_read<=odd_columns[odd_address];
            end
            if(pending && p_vertical!=2) begin
                if(p_two || !p_first_odd)
                    even_columns[p_even_address]<=p_vertical==0 ? p_even_sum:add_channels(even_read,p_even_sum);
                if(p_two || p_first_odd)
                    odd_columns[p_odd_address]<=p_vertical==0 ? p_odd_sum:add_channels(odd_read,p_odd_sum);
            end
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            active<=0;x<=0;y<=0;column<=0;phase<=0;vertical<=0;
            horizontal<=0;source_id<=0;source_ns<=0;
            pending<=0;p_first_odd<=0;p_two<=0;p_sof<=0;p_eol<=0;p_eof<=0;p_vertical<=0;
            p_even_address<=0;p_odd_address<=0;p_even_sum<=0;p_odd_sum<=0;p_id<=0;p_ns<=0;
            out_valid<=0;out_rgb<=0;out_count<=0;out_sof<=0;out_eol<=0;out_eof<=0;
            out_frame_id<=0;out_source_ns<=0;
            frame_starts<=0;frame_completions<=0;frame_aborts<=0;framing_error<=0;
        end else begin
            if(out_valid && out_ready && out_eof) frame_completions<=frame_completions+1'b1;
            if(advance) begin
                out_valid<=pending && p_vertical==2;
                if(pending && p_vertical==2) begin
                    out_rgb<=p_first_odd ? {even_mean,odd_mean}:{odd_mean,even_mean};
                    out_count<=p_two ? 2'd2:2'd1;
                    out_sof<=p_sof;out_eol<=p_eol;out_eof<=p_eof;
                    out_frame_id<=p_id;out_source_ns<=p_ns;
                end
                pending<=0;
                if(accept && framed) begin
                    if(in_sof) begin
                        frame_starts<=frame_starts+1'b1;source_id<=in_frame_id;source_ns<=in_source_ns;
                        if(active) begin frame_aborts<=frame_aborts+1'b1;framing_error<=1;end
                    end
                    if(!legal_eol) begin
                        active<=0;framing_error<=1;
                        frame_aborts<=frame_aborts+((in_sof && active) ? 32'd2:32'd1);
                        x<=0;y<=0;column<=0;phase<=0;vertical<=0;horizontal<=0;
                    end else begin
                        pending<=1;p_first_odd<=wc[0];p_two<=two;p_vertical<=vp;
                        p_even_address<=even_address;p_odd_address<=odd_address;
                        p_even_sum<=wc[0] ? sum1:sum0;p_odd_sum<=wc[0] ? sum0:sum1;
                        p_id<=in_sof ? in_frame_id:source_id;p_ns<=in_sof ? in_source_ns:source_ns;
                        p_sof<=wy==2 && wx==0;p_eol<=vp==2 && in_eol;
                        p_eof<=vp==2 && in_eol && wy==HEIGHT-1;
                        active<=1;
                        vertical<=vp;
                        horizontal<=next_horizontal;
                        phase<=hp==2 ? 2'd0:hp+2'd1;
                        x<=wx+16'd4;column<=wc+(two ? 16'd2:16'd1);
                        if(in_eol) begin
                            x<=0;column<=0;phase<=0;horizontal<=0;
                            vertical<=vp==2 ? 2'd0:vp+2'd1;
                            if(wy==HEIGHT-1) begin active<=0;y<=0;vertical<=0;end
                            else y<=wy+16'd1;
                        end else y<=wy;
                    end
                end
            end
        end
    end
endmodule
`default_nettype wire
