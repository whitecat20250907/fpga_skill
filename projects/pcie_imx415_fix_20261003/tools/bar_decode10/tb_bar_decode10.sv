`timescale 1ns/1ps
module tb_bar_decode10;
reg clk=0,rst_n=0,arvalid=0;
reg [31:0] addr=0;
wire [31:0] new_data,old_data;
wire new_selected,old_selected;
integer checks=0,new_errors=0,old_mismatches=0,old_base0_errors=0;
integer old_version_witnesses=0,base_index,off;
reg test_done=0,old_failure_detected=0;
reg [31:0] base;
always #4 clk=~clk;
read_probe #(.OLD_DECODE(0)) candidate(clk,rst_n,addr,arvalid,new_data,new_selected);
read_probe #(.OLD_DECODE(1)) original(clk,rst_n,addr,arvalid,old_data,old_selected);

// Human-authored address/value golden. It does not parse the production case
// or use its REG_* macros or its selector expression to derive expectations.
function [31:0] register_value;
input [31:0] offset;
begin
case(offset)
32'h40:register_value=3;
32'h44:register_value=1920;
32'h48:register_value=1080;
32'h4c:register_value=1;
32'h50:register_value=32'h10203040;
32'h54:register_value=0;
32'h58:register_value=6220800;
32'h5c:register_value=32'h56440901;
32'h60:register_value=1;
32'h64:register_value=6220864;
32'h68:register_value=32'h87654321;
32'h6c:register_value=0;
32'h70:register_value=32'h10203040;
32'h74:register_value=32'hfd7;
32'h78:register_value=32'h01020304;
32'h7c:register_value=32'h55667788;
32'h80:register_value=1;
32'h84:register_value=32'h5a006337;
32'h88:register_value=32'h10203040;
32'h8c:register_value=32'h07800438;
32'h90:register_value=0;
32'h94:register_value=3;
32'h98:register_value=100;
32'h9c:register_value=2;
32'ha0:register_value=9;
32'ha4:register_value=0;
32'ha8:register_value=32'h22;
32'hac:register_value=32'h01000006;
32'hb0:register_value=32'h01000000;
32'hb4:register_value=32'h01000001;
32'hb8:register_value=32'h01000002;
32'hbc:register_value=32'h01000003;
32'hc0:register_value=32'h01000004;
32'hc4:register_value=32'h01000005;
32'hc8:register_value=32'h00aabbcc;
32'hcc:register_value=270000;
32'hd0:register_value=17;
32'hd4:register_value=31;
32'hd8:register_value=3;
32'hdc:register_value=2;
32'he0:register_value=32'h55;
32'he4:register_value=32'haa;
32'he8:register_value=32'h20100000;
32'hec:register_value=32'h20100001;
32'hf0:register_value=32'h20100002;
32'hf4:register_value=32'h20100003;
32'hf8:register_value=32'h3412cdab;
32'hfc:register_value=32'hb8d5d5af;
32'h100:register_value=32'hcc;
32'h104:register_value=32'h40100000;
32'h108:register_value=32'h40100001;
32'h10c:register_value=32'h40100002;
32'h110:register_value=32'h40100003;
32'h114:register_value=32'h40100004;
32'h118:register_value=32'h40100005;
32'h11c:register_value=32'hd5;
default:register_value=0;
endcase
end
endfunction

task check_read;
input [31:0] base_arg,offset;
reg expected_selection;
reg [31:0] expected;
begin
// Test arguments explicitly define the intended BAR-relative address.
expected_selection=(offset>=32'h40 && offset<=32'h11c);
expected=expected_selection ? register_value(offset) :
    ((offset==32'h128) ? 32'h13579bdf : (32'ha5a50000 | (offset & 32'hffff)));
@(negedge clk);addr=base_arg+offset;arvalid=1;
@(posedge clk);#1;
checks=checks+1;
if(new_selected!==expected_selection || new_data!==expected)begin
new_errors=new_errors+1;
$display("NEW_ERROR base=%08x off=%08x sel=%b exp_sel=%b value=%08x expected=%08x",base_arg,offset,new_selected,expected_selection,new_data,expected);
end
if(old_selected!==expected_selection || old_data!==expected)begin
old_mismatches=old_mismatches+1;
if(base_arg==0)old_base0_errors=old_base0_errors+1;
if(offset==32'h5c && base_arg!=0)begin
old_version_witnesses=old_version_witnesses+1;
$display("OLD_FAIL_WITNESS base=%08x address=%08x version_read=%08x expected=%08x sel=%b",base_arg,addr,old_data,expected,old_selected);
end
end
@(negedge clk);arvalid=0;
@(posedge clk);#1;
if(new_selected!==0)begin new_errors=new_errors+1;$display("NEW_ERROR idle select did not return low");end
end
endtask

initial begin
repeat(3)@(posedge clk);
@(negedge clk);rst_n=1;
for(base_index=0;base_index<4;base_index=base_index+1)begin
// 0x01200000 is the nonzero prefix left by a 26-bit CQ address mask.
case(base_index)0:base=0;1:base=32'h21200000;2:base=32'hfff00000;3:base=32'h01200000;endcase
for(off=32'h40;off<=32'h11c;off=off+4)check_read(base,off);
check_read(base,0);check_read(base,32'h3c);check_read(base,32'h3f);
check_read(base,32'h11d);check_read(base,32'h120);check_read(base,32'h128);
check_read(base,32'h1005c);check_read(base,32'h10100);check_read(base,32'h1fffc);
check_read(base,32'h8005c);
check_read(base,32'hffffc);
end
if(new_errors!=0)$fatal(1,"Candidate failed golden: %0d errors",new_errors);
if(old_mismatches!=168 || old_base0_errors!=0 || old_version_witnesses!=3)
  $fatal(1,"Old negative control did not fail exactly: mismatches=%0d base0=%0d version=%0d",old_mismatches,old_base0_errors,old_version_witnesses);
old_failure_detected=1;
$display("OLD_DECODE_FAIL mismatches=%0d correct_base0=1 version_witnesses=%0d",old_mismatches,old_version_witnesses);
if($test$plusargs("OLD_FATAL"))$fatal(1,"EXPECTED_OLD_UPPER16_ZERO_REGRESSION_DETECTED");
test_done=1;
$display("PASS BAR_DECODE10_PRODUCTION_READ checks=%0d new_errors=%0d old_mismatches=%0d; immediate-read only, NOT AXI backpressure/PCIe/PHY acceptance",checks,new_errors,old_mismatches);
$stop;
end
initial begin #100000;$fatal(1,"TIMEOUT BAR decode selfcheck");end
endmodule
