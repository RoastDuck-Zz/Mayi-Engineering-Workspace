#pragma once

#include "../l2_serial/frame_assembler.h"
#include <cstdint>
#include <string>
#include <vector>

namespace guidedog::l2::ethernet {
struct UdpCounters {
    uint64_t datagrams_total=0, bytes_total=0, wrong_source=0, size_mismatch=0;
    uint64_t malformed_header=0, tail_errors=0, crc_errors=0, unknown_types=0;
    uint64_t cloud_frames=0, imu_frames=0;
};

struct UdpValidation {
    std::vector<Bytes> valid_frames;
};

UdpValidation validate_datagram(const uint8_t* data,size_t size,UdpCounters& counters);
}
