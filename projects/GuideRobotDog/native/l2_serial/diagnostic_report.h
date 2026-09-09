#pragma once
#include "l2_packet_decoder.h"
#include "timestamp_analyzer.h"
#include "sequence_stats.h"
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
    SequenceStats cloud_sequence,imu_sequence;
    bool replay=false;
    size_t requested_read_size=8192;
    uint64_t read_histogram[7]={},zero_reads=0,max_read_size=0;
    double max_processing_gap_ms=0,processing_seconds=0,cpu_seconds=0;
    void read_observed(size_t n) {
        if(!n) {++zero_reads;return;}
        if(n>max_read_size) max_read_size=n;
        size_t bin=n<64?0:n==64?1:n<512?2:n==512?3:n<1024?4:n<4096?5:6;
        ++read_histogram[bin];
    }
    uint64_t bytes=0,valid_frames=0,unknown_frames=0,decode_errors=0;
    uint64_t cloud_frames=0,imu_frames=0,points=0,finite_xyz=0,nonfinite_xyz=0,nonfinite_imu=0;
    uint64_t sequence_changes=0,sequence_duplicates=0;
    Range points_per_frame,x,y,z,intensity;
private:
    std::optional<uint32_t> previous_imu_sequence_;
};
}
