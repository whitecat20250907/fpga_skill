"""ctypes wrapper for the RK3576 parallel LZ77/CRC row decoder."""
from __future__ import annotations

import ctypes
import struct
import time
from pathlib import Path

import numpy as np

LIB = ctypes.CDLL(str(Path(__file__).with_name("libt3codec.so")))
LIB.t3_decode_frame.argtypes = [
    ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t,
    ctypes.c_int, ctypes.c_int,
    ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint64),
    ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint32),
    ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint32),
]
LIB.t3_decode_frame.restype = ctypes.c_int
MONITOR = struct.Struct("<4sBBHIQQIII")


def decode_frame(container: np.ndarray | bytes, height: int = 1080,
                 workers: int = 2) -> tuple[np.ndarray, dict]:
    src = np.ascontiguousarray(
        np.frombuffer(container, dtype=np.uint8).reshape(-1))
    if src.size != height * 2560:
        raise ValueError(f"expected {height*2560} bytes, got {src.size}")
    gray = np.empty((height, 1920), dtype=np.uint8)
    frame_id = ctypes.c_uint32()
    sof_tick = ctypes.c_uint64()
    packet_tick = ctypes.c_uint64()
    packed = ctypes.c_uint32()
    flags = ctypes.c_uint32()
    failed_row = ctypes.c_uint32()
    t0 = time.perf_counter()
    code = LIB.t3_decode_frame(
        src.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), src.nbytes,
        gray.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)), gray.nbytes,
        height, workers, ctypes.byref(frame_id), ctypes.byref(sof_tick),
        ctypes.byref(packet_tick), ctypes.byref(packed),
        ctypes.byref(flags), ctypes.byref(failed_row))
    decode_ms = (time.perf_counter() - t0) * 1000
    if code:
        raise ValueError(f"FPGA packet decode failed: code={code}, row={failed_row.value}")
    info = {
        "frame_id": frame_id.value, "packed_bytes": packed.value,
        "sensor_csi_sof_tick": sof_tick.value,
        "packet_start_tick": packet_tick.value,
        "error_flags": flags.value,
        "decode_ms": round(decode_ms, 3),
        "workers": workers,
    }
    if src[1952:1956].tobytes() == b"TICK":
        (magic, version, error, _reserved, monitor_frame, sof, packet,
         period, hz, overlap) = MONITOR.unpack_from(src, 1952)
        if version != 1 or monitor_frame != frame_id.value:
            raise ValueError("FPGA monitor record does not match frame")
        info.update({
            "previous_frame_period_ticks": period,
            "clock_hz": hz,
            "overlap_count": overlap,
            "measured_input_fps": round(hz / period, 3) if period else None,
            "fpga_pipeline_us": round((packet - sof) * 1e6 / hz, 3)
            if packet >= sof and hz else None,
        })
    if src[1992:1996].tobytes() == b"OVFL":
        info["bridge_overflow_words"] = struct.unpack_from("<I", src, 2000)[0]
    return gray, info
