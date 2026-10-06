#!/usr/bin/env python3
"""Assemble contest item-6 evidence without replacing missing measurements.

Inputs are independently produced by TD, V4L2, RKNN and FPGA metadata.
No software timestamp is presented as a physical camera-to-screen latency.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def load_json(path: Path | None) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path else {}


def match(text: str, pattern: str) -> str:
    result = re.search(pattern, text, flags=re.MULTILINE)
    return result.group(1) if result else "待测"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture", type=Path)
    p.add_argument("--npu", type=Path)
    p.add_argument("--timing", type=Path)
    p.add_argument("--area", type=Path)
    p.add_argument("--fpga-monitor", type=Path)
    p.add_argument("--compression", type=Path)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    cap, npu = load_json(a.capture), load_json(a.npu)
    mon, comp = load_json(a.fpga_monitor), load_json(a.compression)
    if cap.get("capture_origin") == "offline_file":
        # Simulated packet files exercise the decoder but are not board data.
        cap = {}
    cap_hash = cap.get("last_gray_sha256")
    npu_hash = npu.get("input_file_sha256")
    if cap_hash and npu_hash and cap_hash != npu_hash:
        raise ValueError("NPU input bytes do not match the last decoded FPGA frame")
    if not mon and cap.get("fpga_monitors"):
        mon = next((m for m in cap["fpga_monitors"] if m), {})
    if not comp and "packed_bytes_per_frame" in cap:
        comp = {
            "raw_bytes": cap.get("raw_gray_bytes_per_frame"),
            "packed_bytes": cap["packed_bytes_per_frame"][-1],
            "wire_bytes": cap.get("wire_bytes_per_frame"),
            "ratio": cap.get("compression_ratio_vs_gray", [None])[-1],
        }
    live_records = npu.get("records", [])
    npu_median = npu.get("npu_ms_median", npu.get("median_npu_ms", "待测"))
    npu_p95 = npu.get("npu_ms_p95", "待测")
    if npu_p95 == "待测" and live_records:
        durations = sorted(r["npu_ms"] for r in live_records)
        npu_p95 = round(durations[round(0.95 * (len(durations)-1))], 3)
    detections = (len(npu["detections"]) if "detections" in npu else
                  npu.get("total_detections", "待测"))
    npu_source = npu.get("source", "待测")
    npu_basis = ("离线图片，仅验证模型" if
                 npu.get("input_format") == "RGB_IMAGE_OFFLINE" else
                 "RKNNLite；输入来源见 NPU JSON")
    timing = a.timing.read_text(errors="replace") if a.timing else ""
    area = a.area.read_text(errors="replace") if a.area else ""
    lines = [
        "# 赛题三 · 六项基础功能测评记录",
        "",
        "> 只填已测数值；`待测` 表示目前没有相应的物理测量。",
        "",
        "| 指标 | 数值 | 依据与限制 |",
        "|---|---:|---|",
        f"| CSI 连续收到帧数 | {cap.get('frames_verified', cap.get('received_frames', '待测'))} | RK V4L2 捕获；压缩帧需逐行 CRC 验证 |",
        f"| V4L2 有效帧率 | {cap.get('effective_capture_fps_including_io', round(cap['frames_verified']/cap['capture_s_including_file_io'], 3) if cap.get('capture_s_including_file_io') else '待测')} fps | 含启动与文件 I/O，不等于传感器帧率 |",
        f"| FPGA 实测输入帧率 | {mon.get('measured_input_fps') or '待测'} fps | CSI 帧起始之间的 FPGA 时钟计数 |",
        f"| 不同帧数（抽样哈希） | {cap.get('unique_sampled_frame_hashes', '待测')} | 只能辅助辨别静态测试图/真实场景 |",
        f"| CSI 帧起始→FPGA 首包组装 | {mon.get('fpga_pipeline_us') or '待测'} µs | FPGA 同一时基计数；尚未含 RK 接收和显示 |",
        f"| FPGA 行缓存重叠次数 | {mon.get('overlap_count', '待测')} | 应为 0 |",
        f"| FPGA 链路黏滞错误标志 | {mon.get('error_flags', '待测')} | bit 3 是异步 FIFO 曾溢出；须结合累计计数判断稳态 |",
        f"| FPGA FIFO 累计丢弃 64 位字 | {mon.get('bridge_overflow_words', '待测')} | 可能含启流期间；不是当前帧丢弃数 |",
        f"| 本次连续抓帧新增 FIFO 丢弃字 | {cap.get('bridge_overflow_words_added_during_capture') if cap.get('bridge_overflow_words_added_during_capture') is not None else '待测'} | 应为 0；比较首末帧硬件计数 |",
        f"| 光电端到端延迟 | {mon.get('photo_to_response_us', '待测')} µs | 必须接光电探头；软件计时不可代替 |",
        f"| 压缩前字节数 | {comp.get('raw_bytes', '待测')} | 协议规定的原灰度帧大小，RK 核验行数 |",
        f"| 压缩后字节数 | {comp.get('packed_bytes', '待测')} | RK 累加 FPGA 行头长度并逐行核验 CRC；不含容器填充 |",
        f"| 灰度压缩比 | {comp.get('ratio') or '待测'} | 原始灰度字节数 / 实际 LZ77 载荷字节数 |",
        f"| 实际 MIPI 在线字节数 | {comp.get('wire_bytes', '待测')} | 固定 YUYV 容器阶段可能不下降 |",
        f"| NPU 输入来源 | {npu_source} | {npu_basis} |",
        f"| NPU 输入与末帧解码哈希一致 | {'是' if cap_hash and npu_hash else '待测'} | SHA-256；需两个 JSON 均含哈希 |",
        f"| NPU 稳态推理中位数 | {npu_median} ms | RKNNLite；模型和输入图随 JSON |",
        f"| NPU 稳态推理 P95 | {npu_p95} ms | RKNNLite |",
        f"| RK 单帧解码+预处理+推理+后处理 | {npu.get('median_processing_ms', '待测')} ms | 软件分段计时中位数；不含光电采集和显示 |",
        f"| RK 实时处理吞吐 | {npu.get('effective_app_fps', '待测')} fps | live_detect 实时循环；慢于相机时丢弃旧帧 |",
        f"| NPU 识别框数 | {detections} | 检测结果来自当前输入帧 |",
        f"| TD STA 覆盖率 | {match(timing, r'STA coverage\s*:\s*([^\r\n]+)')} | routed timing report |",
        f"| TD 最差建立余量 SWNS | {match(timing, r'SWNS:\s*([^,\r\n]+)')} | 应 ≥ 0 ns 方可签核 |",
        f"| TD 最差保持余量 HWNS | {match(timing, r'HWNS:\s*([^,\r\n]+)')} | 应 ≥ 0 ns 方可签核 |",
        f"| LUT6 用量 | {match(area, r'^#lut6\s+(\d+\s+out of\s+\d+[^\r\n]*)')} | TD 布线资源报告 |",
        f"| ERAM 用量 | {match(area, r'^#eram\s+(\d+\s+out of\s+\d+[^\r\n]*)')} | TD 布线资源报告 |",
        f"| DSP 用量 | {match(area, r'^#dsp\s+(\d+\s+out of\s+\d+[^\r\n]*)')} | TD 布线资源报告 |",
        "",
        "## 文件依据",
        "",
    ]
    for label, path in (("V4L2", a.capture), ("RKNN", a.npu),
                        ("TD timing", a.timing), ("TD area", a.area),
                        ("FPGA monitor", a.fpga_monitor),
                        ("compression", a.compression)):
        lines.append(f"- {label}: `{path}`" if path else f"- {label}: 待测")
    lines.append("")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text("\n".join(lines), encoding="utf-8")
    print(a.out)


if __name__ == "__main__":
    main()
