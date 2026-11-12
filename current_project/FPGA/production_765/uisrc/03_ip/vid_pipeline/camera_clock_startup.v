// Independent IMX415 startup candidate; not yet in the frozen FPGA file set.
// Digital sequencing only: it does not prove rail timing, PLL analog lock,
// the IO clock waveform or that VID005 routes this clock to the sensor.
// system_reset_n must remain low until the board's sensor rails are valid.
// Caller supplies the existing 24 MHz control clock and native PLL 27 MHz clock.
// No divider/toggle flop, ODDR or raw-lock combinational clock gate is used.
module camera_clock_startup #(
    parameter integer CONTROL_CLOCK_HZ = 24000000,
    parameter integer XCLR_LOW_US = 10,
    parameter integer XCLR_HIGH_TO_MCLK_US = 2,
    parameter integer MCLK_ACK_TO_CONFIG_US = 50,
    parameter integer RESET_SYNC_STAGES = 3,
    parameter integer REQUEST_SYNC_STAGES = 2,
    parameter integer ACK_SYNC_STAGES = 2,
    parameter integer LOCK_STABLE_CYCLES = 8,
    parameter integer ACK_STABLE_CYCLES = 2
)(
    input wire clock24,
    input wire clock27,
    input wire pll27_lock_raw,
    input wire ui_lock_raw,
    input wire system_reset_n,
    output reg sensor_xclr,
    output wire sensor_mclk,
    output reg config_reset_n,
    output wire [15:0] status
);
// Legal parameters: frequency >0, all times/cycle counts >=1, sync stages >=2.
// Integer microsecond waits use ceiling conversion plus one guard control cycle.
// This gives margin at the stated nominal control frequency; hardware frequency
// tolerance, routing delay, duty cycle and recovery/removal require real checks.
function integer microsecond_cycles;
    input integer usecs;
    begin
        microsecond_cycles=(CONTROL_CLOCK_HZ/1000000)*usecs +
            (((CONTROL_CLOCK_HZ%1000000)*usecs+999999)/1000000)+1;
    end
endfunction
function integer max_value;
    input integer a,b;
    begin max_value=(a>b)?a:b;end
endfunction
function integer counter_width;
    input integer maximum;
    integer value;
    begin
        value=maximum-1;counter_width=0;
        while(value>0)begin counter_width=counter_width+1;value=value>>1;end
        if(counter_width<1)counter_width=1;
    end
endfunction
localparam integer LOW_CYCLES=microsecond_cycles(XCLR_LOW_US);
localparam integer HIGH_CYCLES=microsecond_cycles(XCLR_HIGH_TO_MCLK_US);
localparam integer CONFIG_CYCLES=microsecond_cycles(MCLK_ACK_TO_CONFIG_US);
localparam integer MAX_CYCLES=max_value(max_value(LOW_CYCLES,HIGH_CYCLES),
    max_value(CONFIG_CYCLES,max_value(LOCK_STABLE_CYCLES,ACK_STABLE_CYCLES)));
localparam integer TIMER_BITS=counter_width(MAX_CYCLES);
localparam [2:0] WAIT_LOCK=3'd0,HOLD_XCLR_LOW=3'd1,HOLD_XCLR_HIGH=3'd2,
    WAIT_MCLK_ACK=3'd3,MCLK_SETTLE=3'd4,RUN=3'd5;
reg [2:0] state;
reg [TIMER_BITS-1:0] delay_count;
reg lock_qualified24,mclk_request24,ack_stable24;

// Raw locks affect only asynchronous reset assertion. A lock loss never
// directly ANDs with clock27. Reset release needs clock24 edges and stability.
wire control_async_reset_n=system_reset_n & pll27_lock_raw & ui_lock_raw;
(* async_reg="true" *) reg [RESET_SYNC_STAGES-1:0] control_reset_sync;
always @(posedge clock24 or negedge control_async_reset_n)begin
    if(!control_async_reset_n)control_reset_sync<={RESET_SYNC_STAGES{1'b0}};
    else control_reset_sync<={control_reset_sync[RESET_SYNC_STAGES-2:0],1'b1};
end
wire control_reset_n=control_reset_sync[RESET_SYNC_STAGES-1];

// XCLR is asserted by the control reset first; ONLY this already-low XCLR may
// asynchronously clear the 27 MHz forwarding gate. Release is synchronized in
// the 27 MHz domain. Thus asynchronous truncation is confined to sensor reset.
(* async_reg="true" *) reg [RESET_SYNC_STAGES-1:0] clock27_reset_sync;
always @(posedge clock27 or negedge sensor_xclr)begin
    if(!sensor_xclr)clock27_reset_sync<={RESET_SYNC_STAGES{1'b0}};
    else clock27_reset_sync<={clock27_reset_sync[RESET_SYNC_STAGES-2:0],1'b1};
end
wire clock27_reset_n=clock27_reset_sync[RESET_SYNC_STAGES-1];
(* async_reg="true" *) reg [REQUEST_SYNC_STAGES-1:0] request_sync27;
always @(posedge clock27 or negedge clock27_reset_n)begin
    if(!clock27_reset_n)request_sync27<={REQUEST_SYNC_STAGES{1'b0}};
    else request_sync27<={request_sync27[REQUEST_SYNC_STAGES-2:0],mclk_request24};
end
reg mclk_gate_enable27;
always @(negedge clock27 or negedge clock27_reset_n)begin
    if(!clock27_reset_n)mclk_gate_enable27<=1'b0;
    else mclk_gate_enable27<=request_sync27[REQUEST_SYNC_STAGES-1];
end
// Enable changes at a falling source edge. During normal startup this forwards
// complete source-clock high/low pulses at 27 MHz, rather than halving it.
assign sensor_mclk=clock27 & mclk_gate_enable27;

// This ACK reports a latched forwarding enable, NOT proof of clock frequency
// or continued clock edges. Use the independent frequency monitor for that.
(* async_reg="true" *) reg [ACK_SYNC_STAGES-1:0] ack_sync24;
always @(posedge clock24 or negedge control_reset_n)begin
    if(!control_reset_n)ack_sync24<={ACK_SYNC_STAGES{1'b0}};
    else ack_sync24<={ack_sync24[ACK_SYNC_STAGES-2:0],mclk_gate_enable27};
end
wire mclk_ack24=ack_sync24[ACK_SYNC_STAGES-1];

always @(posedge clock24 or negedge control_reset_n)begin
    if(!control_reset_n)begin
        state<=WAIT_LOCK;delay_count<=0;
        sensor_xclr<=0;config_reset_n<=0;
        lock_qualified24<=0;mclk_request24<=0;ack_stable24<=0;
    end else begin
        case(state)
            WAIT_LOCK:begin
                sensor_xclr<=0;config_reset_n<=0;mclk_request24<=0;
                lock_qualified24<=0;ack_stable24<=0;
                if(delay_count==LOCK_STABLE_CYCLES-1)begin
                    delay_count<=0;lock_qualified24<=1;state<=HOLD_XCLR_LOW;
                end else delay_count<=delay_count+1'b1;
            end
            HOLD_XCLR_LOW:begin
                if(delay_count==LOW_CYCLES-1)begin
                    delay_count<=0;sensor_xclr<=1;state<=HOLD_XCLR_HIGH;
                end else delay_count<=delay_count+1'b1;
            end
            HOLD_XCLR_HIGH:begin
                if(delay_count==HIGH_CYCLES-1)begin
                    delay_count<=0;mclk_request24<=1;state<=WAIT_MCLK_ACK;
                end else delay_count<=delay_count+1'b1;
            end
            WAIT_MCLK_ACK:begin
                // No ACK/no 27 MHz clock means I2C stays in reset, without
                // inventing an elapsed-clock acknowledgment in the 24 MHz FSM.
                if(mclk_ack24)begin
                    if(delay_count==ACK_STABLE_CYCLES-1)begin
                        delay_count<=0;ack_stable24<=1;state<=MCLK_SETTLE;
                    end else delay_count<=delay_count+1'b1;
                end else delay_count<=0;
            end
            MCLK_SETTLE:begin
                if(!mclk_ack24)begin
                    sensor_xclr<=0;config_reset_n<=0;mclk_request24<=0;
                    lock_qualified24<=0;ack_stable24<=0;delay_count<=0;state<=WAIT_LOCK;
                end else if(delay_count==CONFIG_CYCLES-1)begin
                    delay_count<=0;config_reset_n<=1;state<=RUN;
                end else delay_count<=delay_count+1'b1;
            end
            RUN:begin
                if(!mclk_ack24)begin
                    sensor_xclr<=0;config_reset_n<=0;mclk_request24<=0;
                    lock_qualified24<=0;ack_stable24<=0;delay_count<=0;state<=WAIT_LOCK;
                end
            end
            default:begin
                sensor_xclr<=0;config_reset_n<=0;mclk_request24<=0;
                lock_qualified24<=0;ack_stable24<=0;delay_count<=0;state<=WAIT_LOCK;
            end
        endcase
    end
end
// [0] control reset synchronously released; [1] locks qualified in clock24;
// [2] XCLR high; [3] MCLK request; [4] latched gate ACK synchronized to clock24;
// [5] ACK stable for ACK_STABLE_CYCLES; [6] configuration/I2C reset released;
// [7] reserved 0; [10:8] FSM state (0 lock,1 low,2 high,3 ack,4 settle,5 run);
// [15:11] reserved 0. These are control-domain status, not raw PLL truth.
assign status={5'b0,state,1'b0,config_reset_n,ack_stable24,mclk_ack24,
    mclk_request24,sensor_xclr,lock_qualified24,control_reset_n};
endmodule
