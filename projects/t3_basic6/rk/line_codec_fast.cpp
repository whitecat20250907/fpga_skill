// RK3576 R1: byte-exact four-lane row decoder with parallel CRC checks.
// Build on RK: g++ -O3 -std=c++17 -fopenmp -fPIC -shared -o libt3codec.so line_codec_fast.cpp
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <climits>

#ifdef _OPENMP
#include <omp.h>
#endif

namespace {
constexpr int kWidth = 1920;
constexpr int kLaneBytes = 480;
constexpr int kContainerBytes = 2560;
constexpr int kHeaderBytes = 32;

uint16_t u16(const uint8_t* p) {
    return uint16_t(p[0]) | (uint16_t(p[1]) << 8);
}
uint32_t u32(const uint8_t* p) {
    return uint32_t(p[0]) | (uint32_t(p[1]) << 8) |
           (uint32_t(p[2]) << 16) | (uint32_t(p[3]) << 24);
}
uint64_t u64(const uint8_t* p) {
    return uint64_t(u32(p)) | (uint64_t(u32(p + 4)) << 32);
}

const std::array<uint32_t, 256>& crc_table() {
    static const std::array<uint32_t, 256> table = [] {
        std::array<uint32_t, 256> result{};
        for (unsigned n = 0; n < 256; ++n) {
            uint32_t c = n;
            for (int bit = 0; bit < 8; ++bit)
                c = (c >> 1) ^ ((c & 1) ? 0xEDB88320u : 0u);
            result[n] = c;
        }
        return result;
    }();
    return table;
}

bool decode_lane(const uint8_t* src, int len, int mode, uint8_t* delta) {
    if (mode == 0) {
        if (len != kLaneBytes) return false;
        std::memcpy(delta, src, kLaneBytes);
        return true;
    }
    if (mode != 1 || len > kLaneBytes) return false;
    int in = 0, out = 0;
    while (in < len) {
        uint8_t value = src[in++];
        if (value != 0xFF) {
            if (out >= kLaneBytes) return false;
            delta[out++] = value;
        } else {
            if (in >= len) return false;
            uint8_t ctrl = src[in++];
            if (ctrl == 0) {
                if (out >= kLaneBytes) return false;
                delta[out++] = 0xFF;
            } else if (ctrl & 0x80) {
                int count = (ctrl & 0x7F) + 3;
                if (out == 0 || out + count > kLaneBytes) return false;
                std::memset(delta + out, delta[out - 1], count);
                out += count;
            } else return false;
        }
    }
    return out == kLaneBytes;
}

bool decode_row(const uint8_t* row, uint8_t* gray, int row_index,
                uint32_t expected_frame, uint32_t& packed) {
    if (std::memcmp(row, "LZ4R", 4) || row[4] != 1 ||
        (row[5] & 0x0F) != 1 || u16(row + 6) != row_index ||
        u32(row + 8) != expected_frame || u16(row + 12) != kWidth)
        return false;
    int lengths[4];
    int total = 0;
    for (int lane = 0; lane < 4; ++lane) {
        lengths[lane] = u16(row + 20 + 2 * lane);
        if (lengths[lane] > kLaneBytes || row[16 + lane] > 1)
            return false;
        total += lengths[lane];
    }
    if (total != u16(row + 14)) return false;
    uint8_t lane_data[4][kLaneBytes];
    uint8_t delta[4][kLaneBytes];
    const uint8_t* payload = row + kHeaderBytes;
    for (int pair = 0; pair < kLaneBytes / 2; ++pair) {
        for (int lane = 0; lane < 4; ++lane) {
            lane_data[lane][2 * pair] = payload[8 * pair + 2 * lane];
            lane_data[lane][2 * pair + 1] = payload[8 * pair + 2 * lane + 1];
        }
    }
    for (int lane = 0; lane < 4; ++lane) {
        if (!decode_lane(lane_data[lane], lengths[lane], row[16 + lane],
                         delta[lane])) return false;
        uint8_t pixel = 0;
        for (int x = 0; x < kLaneBytes; ++x) {
            pixel = uint8_t(pixel + delta[lane][x]);
            gray[4 * x + lane] = pixel;
        }
    }
    uint32_t crc = 0xFFFFFFFFu;
    const auto& table = crc_table();
    for (int x = 0; x < kWidth; ++x)
        crc = table[(crc ^ gray[x]) & 0xFF] ^ (crc >> 8);
    if ((crc ^ 0xFFFFFFFFu) != u32(row + 28)) return false;
    packed = total;
    return true;
}
}  // namespace

extern "C" int t3_decode_frame(const uint8_t* src, std::size_t src_len,
                                uint8_t* dst, std::size_t dst_len,
                                int height, int workers, uint32_t* frame_id,
                                uint64_t* sof_tick, uint64_t* packet_tick,
                                uint32_t* packed_total,
                                uint32_t* error_flags,
                                uint32_t* failed_row) {
    if (!src || !dst || !frame_id || !sof_tick || !packet_tick ||
        !packed_total || !error_flags || !failed_row ||
        height <= 0 || height > 2048 || workers < 1 || workers > 16 ||
        src_len != std::size_t(height) * kContainerBytes ||
        dst_len != std::size_t(height) * kWidth)
        return -1;
    const uint32_t expected_frame = u32(src + 8);
    unsigned total = 0;
    unsigned first_bad = UINT_MAX;
#ifdef _OPENMP
    #pragma omp parallel for num_threads(workers) reduction(+:total) reduction(min:first_bad)
#endif
    for (int row = 0; row < height; ++row) {
        uint32_t row_packed = 0;
        if (decode_row(src + row * kContainerBytes,
                       dst + row * kWidth, row, expected_frame, row_packed))
            total += row_packed;
        else if (unsigned(row) < first_bad)
            first_bad = unsigned(row);
    }
    *failed_row = first_bad;
    if (first_bad != UINT_MAX) return -2;
    *frame_id = expected_frame;
    *packed_total = total;
    *sof_tick = 0;
    *packet_tick = 0;
    *error_flags = 0;
    const uint8_t* monitor = src + kHeaderBytes + kWidth;
    if (!std::memcmp(monitor, "TICK", 4)) {
        if (monitor[4] != 1 || u32(monitor + 8) != expected_frame)
            return -3;
        *error_flags = monitor[5];
        *sof_tick = u64(monitor + 12);
        *packet_tick = u64(monitor + 20);
    }
    return 0;
}
