#pragma once
#include "frame_assembler.h"
#include <array>
#include <optional>
namespace guidedog::l2 {
struct Point { double x,y,z,intensity,time; uint32_t ring; };
struct CloudFrame { std::vector<Point> points; uint32_t declared_points=0; };
struct ImuFrame {
    std::array<double,4> quaternion{};
    std::array<double,3> angular_velocity{},linear_acceleration{};
    uint32_t nonfinite=0;
};
struct DecodedPacket {
    bool valid=false,known=false;
    uint32_t type=0,declared_length=0;
    std::optional<uint32_t> sequence,raw_sec,raw_nsec;
    std::optional<double> raw_timestamp;
    std::optional<CloudFrame> cloud;
    std::optional<ImuFrame> imu;
};
DecodedPacket decode(const Bytes& frame);
}
