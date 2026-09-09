#pragma once
#include "l2_packet_decoder.h"
#include "timestamp_analyzer.h"
#include <ostream>
#include <string>
namespace guidedog::l2 {
std::string json_string(const std::string& s);
void number(std::ostream& out,std::optional<double> v);
struct Range {
    std::optional<double> min,max;
    void add(double value);
};
class DiagnosticReport {
public:
    DiagnosticReport(double num,double den):cloud_time(num,den),imu_time(num,den) {}
    void observe(const DecodedPacket& packet,double host);
    void json(std::ostream& out,const std::string& device,unsigned baud,double runtime,
              const FrameAssembler& assembler,const std::string& status,
              const std::string& error,bool clean_exit,double num,double den) const;
    TimestampAnalyzer cloud_time,imu_time;
    uint64_t bytes=0,valid_frames=0,unknown_frames=0,decode_errors=0;
    uint64_t cloud_frames=0,imu_frames=0,points=0,finite_xyz=0,nonfinite_xyz=0,nonfinite_imu=0;
    uint64_t sequence_changes=0,sequence_duplicates=0;
    Range points_per_frame,x,y,z,intensity;
private:
    std::optional<uint32_t> previous_imu_sequence_;
};
}
