#include "diagnostic_report.h"
#include <cmath>
#include <iomanip>
#include <sstream>
namespace guidedog::l2 {
std::string json_string(const std::string& s) {
    std::ostringstream o;o<<'"';
    for(unsigned char c:s) {
        if(c=='"' || c=='\\') o<<'\\'<<c;
        else if(c<32 || c>=127) o<<"\\u00"<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(c)<<std::dec;
        else o<<c;
    }
    o<<'"';return o.str();
}
void number(std::ostream& out,std::optional<double> v) {
    if(v && std::isfinite(*v)) out<<std::setprecision(17)<<*v;
    else out<<"null";
}
void Range::add(double v) {
    if(!std::isfinite(v)) return;
    if(!min || v<*min) min=v;
    if(!max || v>*max) max=v;
}
void DiagnosticReport::observe(const DecodedPacket& d,double host) {
    ++valid_frames;
    if(!d.valid) {++decode_errors;return;}
    if(!d.known) ++unknown_frames;
    if(d.cloud) {
        ++cloud_frames; cloud_time.add(*d.raw_timestamp,host);cloud_sequence.add(*d.sequence);
        const auto& pts=d.cloud->points;points+=pts.size();points_per_frame.add(double(pts.size()));
        for(const auto& p:pts) {
            bool finite=std::isfinite(p.x)&&std::isfinite(p.y)&&std::isfinite(p.z);
            if(finite) {++finite_xyz;x.add(p.x);y.add(p.y);z.add(p.z);} else ++nonfinite_xyz;
            intensity.add(p.intensity);
        }
    }
    if(d.imu) {
        ++imu_frames;imu_time.add(*d.raw_timestamp,host);imu_sequence.add(*d.sequence);nonfinite_imu+=d.imu->nonfinite;
        if(previous_imu_sequence_) {
            if(*previous_imu_sequence_==*d.sequence) ++sequence_duplicates;
            else ++sequence_changes;
        }
        previous_imu_sequence_=d.sequence;
    }
}
static void timestamps(std::ostream& o,const TimestampAnalyzer& t,bool replay) {
    o<<"{\"first_raw\":";number(o,t.first_raw);
    o<<",\"last_raw\":";number(o,t.last_raw);
    o<<",\"delta\":";number(o,t.delta());
    o<<",\"first_host_monotonic\":";number(o,replay?std::nullopt:t.first_host);
    o<<",\"last_host_monotonic\":";number(o,replay?std::nullopt:t.last_host);
    o<<",\"host_elapsed\":";number(o,replay?std::nullopt:t.host_elapsed());
    o<<",\"host_ratio\":";number(o,replay?std::nullopt:t.ratio());
    o<<",\"first_corrected\":";number(o,t.corrected_first);
    o<<",\"last_corrected\":";number(o,t.corrected_last);
    o<<",\"backsteps\":"<<t.backsteps<<",\"invalid\":"<<t.invalid<<'}';
}
void DiagnosticReport::json(std::ostream& o,const std::string& device,unsigned baud,double runtime,
        const FrameAssembler& a,const std::string& status,const std::string& error,
        bool clean_exit,double num,double den) const {
    o<<"{\n\"device\":"<<json_string(device)<<",\"baudrate\":"<<baud<<",\"runtime_seconds\":";number(o,runtime);
    o<<",\"status\":"<<json_string(status)<<",\"error\":"<<(error.empty()?"null":json_string(error));
    o<<",\"clean_exit\":"<<(clean_exit?"true":"false")<<",\"bytes_received\":"<<bytes;
    o<<",\"valid_frames\":"<<valid_frames<<",\"crc_errors\":"<<a.crc_errors;
    o<<",\"framing_errors\":"<<a.framing_errors<<",\"trailing_bytes\":"<<a.pending();
    o<<",\"discarded_bytes\":"<<a.discarded_bytes;
    o<<",\"unknown_frames\":"<<unknown_frames<<",\"decode_errors\":"<<decode_errors;
    o<<",\"cloud_frames\":"<<cloud_frames<<",\"imu_frames\":"<<imu_frames;
    o<<",\"cloud_timestamp\":";timestamps(o,cloud_time,replay);
    o<<",\"imu_timestamp\":";timestamps(o,imu_time,replay);
    o<<",\"cloud_sequence\":";cloud_sequence.json(o);
    o<<",\"imu_sequence\":";imu_sequence.json(o);
    o<<",\"read_size\":"<<requested_read_size<<",\"zero_length_reads_or_polls\":"<<zero_reads;
    o<<",\"max_read_size\":"<<max_read_size<<",\"max_processing_gap_ms\":";number(o,max_processing_gap_ms);
    o<<",\"processing_seconds\":";number(o,processing_seconds);
    o<<",\"cpu_seconds\":";number(o,cpu_seconds);
    o<<",\"read_size_histogram\":{";
    const char* bins[]={"1-63","64","65-511","512","513-1023","1024-4095","4096+"};
    for(size_t i=0;i<7;++i) {if(i)o<<',';o<<json_string(bins[i])<<':'<<read_histogram[i];}o<<'}';
    o<<",\"replay\":"<<(replay?"true":"false");
    o<<",\"time_scale_num\":";number(o,num);o<<",\"time_scale_den\":";number(o,den);
    o<<",\"imu_rate\":";number(o,imu_frames && runtime>0?std::optional<double>(imu_frames/runtime):std::nullopt);
    o<<",\"imu_nonfinite_values\":"<<nonfinite_imu;
    o<<",\"imu_sequence_changes\":"<<sequence_changes<<",\"imu_sequence_duplicates\":"<<sequence_duplicates;
    o<<",\"confirmed_packet_loss\":null,\"point_stats\":{\"points_total\":"<<points;
    o<<",\"points_per_frame_min\":";number(o,points_per_frame.min);
    o<<",\"points_per_frame_max\":";number(o,points_per_frame.max);
    o<<",\"points_per_frame_mean\":";number(o,cloud_frames?std::optional<double>(double(points)/cloud_frames):std::nullopt);
    o<<",\"finite_xyz_count\":"<<finite_xyz<<",\"nonfinite_xyz_count\":"<<nonfinite_xyz;
    o<<",\"x_min\":";number(o,x.min);o<<",\"x_max\":";number(o,x.max);
    o<<",\"y_min\":";number(o,y.min);o<<",\"y_max\":";number(o,y.max);
    o<<",\"z_min\":";number(o,z.min);o<<",\"z_max\":";number(o,z.max);
    o<<",\"intensity_min\":";number(o,intensity.min);o<<",\"intensity_max\":";number(o,intensity.max);
    o<<"},\"safe_device_writes\":{\"work_mode_write\":false,\"time_sync_write\":false,\"reset\":false}}\n";
}
}
