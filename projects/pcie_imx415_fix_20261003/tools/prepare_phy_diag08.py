#!/usr/bin/env python3
"""Stage two source candidates and exact diffs; never edit the frozen FPGA tree."""
from pathlib import Path
import difflib
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools' / 'phy_diag08'


def once(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'Expected exactly one source anchor: {old!r}')
    return text.replace(old, new)


def main():
    if OUT.exists():
        raise RuntimeError(f'Refusing to overwrite staged candidate: {OUT}')
    OUT.mkdir()
    files = {
        'cam_video_source.v': ROOT / 'fpga/uisrc/03_ip/vid_pipeline/cam_video_source.v',
        'mipi_csi_rx.v': ROOT / 'fpga/uisrc/03_ip/mipi_csi_2/mipi_csi_rx.v',
    }
    original = {name: path.read_bytes() for name, path in files.items()}
    cam = original['cam_video_source.v'].decode('latin1')
    rx = original['mipi_csi_rx.v'].decode('latin1')
    cam = once(cam, '    output wire [223:0] csi_snapshot,', '''    // Shadow command lives in user_clk; held-bus CDC is inside mipi_csi_rx.
    input wire [6:0] phy_control_shadow, // bit6 override enable, bits5:0 tap
    output wire [223:0] phy_diag0, phy_diag1, // [223:192] source byte-clock cycles
    output wire [31:0] phy_diag0_status, phy_diag1_status,
    output wire [31:0] phy_diag0_clock_delta, phy_diag1_clock_delta,
    output wire [223:0] csi_snapshot,''')
    cam = once(cam, '    wire [191:0] csi_stats;', '''    wire [191:0] csi_stats;
    wire [191:0] phy_diag0_byte, phy_diag1_byte;
    // Both diagnostic buses originate in BYTE clock, not UI clock. Each
    // snapshot has a coherent hold/ack transfer and its own reset synchronizers.
    // Default PERIOD is destination user_clk cycles (12.5M = 100ms at 125MHz).
    csi_stats_snapshot u_phy_diag0_snapshot (
        .src_clk(mipi_div_clk_out), .dst_clk(user_clk), .rst_n(user_rst_n),
        .src_stats(phy_diag0_byte), .snapshot(phy_diag0),
        .status(phy_diag0_status), .clock_delta(phy_diag0_clock_delta));
    csi_stats_snapshot u_phy_diag1_snapshot (
        .src_clk(mipi_div_clk_out), .dst_clk(user_clk), .rst_n(user_rst_n),
        .src_stats(phy_diag1_byte), .snapshot(phy_diag1),
        .status(phy_diag1_status), .clock_delta(phy_diag1_clock_delta));''')
    cam = once(cam, '        .I_debug_button         (debug_button),', '''        .I_debug_button         (debug_button),
        .I_phy_control_shadow   (phy_control_shadow),
        .O_phy_diag0            (phy_diag0_byte),
        .O_phy_diag1            (phy_diag1_byte),''')
    rx = once(rx, 'input wire                I_debug_button  ,', '''input wire                I_debug_button  ,
    // Seven-bit command is asynchronous to BYTE clock but belongs to the
    // m_axis_video_aclk source domain. Never synchronize these bits separately.
    input wire [6:0] I_phy_control_shadow,
    output wire [191:0] O_phy_diag0, O_phy_diag1,''')
    rx = once(rx, '    reg [1:0] delay_done_sync;', '''    reg [1:0] delay_done_sync;
    wire [31:0] phy_raw_bytes;
    wire phy_sampler_reset_n_x4;
    (* async_reg="true" *) reg [2:0] phy_sampler_reset_sync;
    // One status bit crosses from the HSx4 sampler-reset domain. Do not sample
    // the raw x4 signal in the byte-domain diagnostic held bus.
    always @(posedge w_hs_div_clk or negedge w_reset_out)
        if(!w_reset_out) phy_sampler_reset_sync<=3'b000;
        else phy_sampler_reset_sync<={phy_sampler_reset_sync[1:0],phy_sampler_reset_n_x4};
    wire [223:0] phy_cmd_snapshot;
    wire [6:0] phy_control_byte=phy_cmd_snapshot[6:0];
    // Existing module's request timer is in dst_clk. PERIOD125000 means
    // ~1.122ms at 111.375MHz BYTE clock, not 1ms in the 125MHz source domain.
    // Source held bus includes user-domain source_cycles in snapshot[223:192].
    csi_stats_snapshot #(.PERIOD(125000)) u_phy_control_snapshot (
        .src_clk(m_axis_video_aclk), .dst_clk(w_hs_div_clk), .rst_n(I_reset_n),
        .src_stats({185'd0,I_phy_control_shadow}), .snapshot(phy_cmd_snapshot),
        .status(), .clock_delta());
    reg [31:0] phy_lane0_valid_cycles,phy_lane1_valid_cycles;
    reg [31:0] phy_lane2_valid_cycles,phy_lane3_valid_cycles;
    reg [31:0] phy_payload_beats,phy_word_valid_cycles,phy_packet_errors;
    reg [31:0] phy_current_payload_lines,phy_last_frame_payload_lines,phy_frame_starts;
    reg [7:0] phy_sticky_valid;
    // Sticky bit7 error pulse, bit6 FS, bit5 payload-valid, bit4 aligned word,
    // bits3:0 aligned lane-valid. Counts remain active before auto calibration
    // and capture_armed; packet parser I_enable still controls protocol itself.
    wire [7:0] phy_valid_now={w_packet_error,w_vsync_out,w_payload_valid,
        w_word_align_data_vaild,w_rx_byte_data_align_vaild};
    always @(posedge w_hs_div_clk or negedge w_reset_out) begin
        if(!w_reset_out) begin
            phy_lane0_valid_cycles<=0;phy_lane1_valid_cycles<=0;
            phy_lane2_valid_cycles<=0;phy_lane3_valid_cycles<=0;
            phy_payload_beats<=0;phy_word_valid_cycles<=0;phy_packet_errors<=0;
            phy_current_payload_lines<=0;phy_last_frame_payload_lines<=0;
            phy_frame_starts<=0;phy_sticky_valid<=0;
        end else begin
            if(w_rx_byte_data_align_vaild[0]) phy_lane0_valid_cycles<=phy_lane0_valid_cycles+1'b1;
            if(w_rx_byte_data_align_vaild[1]) phy_lane1_valid_cycles<=phy_lane1_valid_cycles+1'b1;
            if(w_rx_byte_data_align_vaild[2]) phy_lane2_valid_cycles<=phy_lane2_valid_cycles+1'b1;
            if(w_rx_byte_data_align_vaild[3]) phy_lane3_valid_cycles<=phy_lane3_valid_cycles+1'b1;
            if(w_payload_valid) phy_payload_beats<=phy_payload_beats+1'b1;
            if(w_word_align_data_vaild) phy_word_valid_cycles<=phy_word_valid_cycles+1'b1;
            if(w_packet_error) phy_packet_errors<=phy_packet_errors+1'b1;
            phy_sticky_valid<=phy_sticky_valid | phy_valid_now;
            // Payload-last means a parsed RAW10 payload boundary, not CRC-good
            // line acceptance. A later CRC error does not erase this observation.
            // If FS and last coincide, last belongs to the new frame here.
            if(w_vsync_out) begin
                phy_frame_starts<=phy_frame_starts+1'b1;
                phy_last_frame_payload_lines<=phy_current_payload_lines;
                phy_current_payload_lines<=w_payload_valid&&w_payload_last ? 32'd1 : 32'd0;
            end else if(w_payload_valid&&w_payload_last)
                phy_current_payload_lines<=phy_current_payload_lines+1'b1;
        end
    end
    // Low-first BAR-friendly layout. lane0 valid-cycles is bits31:0.
    assign O_phy_diag0={{O_dbg_mipi,O_dbg_delay,phy_sampler_reset_sync[2],phy_control_byte,phy_sticky_valid},
        phy_raw_bytes,phy_lane3_valid_cycles,phy_lane2_valid_cycles,
        phy_lane1_valid_cycles,phy_lane0_valid_cycles};
    assign O_phy_diag1={phy_payload_beats,phy_word_valid_cycles,phy_packet_errors,
        phy_current_payload_lines,phy_last_frame_payload_lines,phy_frame_starts};''')
    rx = once(rx, '.I_debug_button(I_debug_button),', '''.I_debug_button(I_debug_button),
    .I_override_enable          (phy_control_byte[6]),
    .I_override_tap             (phy_control_byte[5:0]),
    .O_dbg_raw_bytes            (phy_raw_bytes),
    .O_sampler_reset_n          (phy_sampler_reset_n_x4),''')
    # Board is strictly4lane; reject unsupported lane-width instead of silently
    # truncating lane bits or indexing nonexistent lanes. Simulation assertion
    # is synthesis-off and does not alter the frozen protocol datapath.
    rx = once(rx, '    wire [MIPI_LAN-1:0]     w_rx_byte_data_align_vaild;', '''    // synthesis translate_off
    initial if(MIPI_LAN!=4) $fatal(1,"PHY_DIAG08 requires four lanes for fixed diagnostic layout");
    // synthesis translate_on
    wire [MIPI_LAN-1:0]     w_rx_byte_data_align_vaild;''')
    candidate = {'cam_video_source.v': cam, 'mipi_csi_rx.v': rx}
    manifest = {'scope': 'Candidates only; frozen FPGA sources are not changed.', 'files': {}}
    for name, content in candidate.items():
        data = content.encode('latin1')
        (OUT/name).write_bytes(data)
        diff = ''.join(difflib.unified_diff(original[name].decode('latin1').splitlines(True),
            content.splitlines(True), fromfile='main07/'+name, tofile='candidate08/'+name))
        (OUT/(name+'.diff')).write_text(diff, encoding='utf-8')
        manifest['files'][name] = {'source': str(files[name]), 'source_sha256': hashlib.sha256(original[name]).hexdigest(),
                                  'candidate_sha256': hashlib.sha256(data).hexdigest()}
        if files[name].read_bytes() != original[name]:
            raise RuntimeError('Frozen source changed concurrently; candidate provenance requires review')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))


if __name__ == '__main__':
    main()
