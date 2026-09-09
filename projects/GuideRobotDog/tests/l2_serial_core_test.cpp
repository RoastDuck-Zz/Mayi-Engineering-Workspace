#include "frame_assembler.h"
#include "l2_packet_decoder.h"
#include "timestamp_analyzer.h"
#include "sequence_stats.h"
#include <cmath>
#include <fstream>
#include <iostream>
#include <stdexcept>
using namespace guidedog::l2;
static int checks=0;
void check(bool ok, const char* label) {
    ++checks; if (!ok) throw std::runtime_error(label);
}
Bytes load(const std::string& p) {
    std::ifstream f(p, std::ios::binary);
    if (!f) throw std::runtime_error("fixture missing");
    return Bytes(std::istreambuf_iterator<char>(f), {});
}
void put32(Bytes& b, size_t p, uint32_t v) {
    for (int i=0;i<4;++i) b[p+i]=static_cast<uint8_t>(v>>(i*8));
}
void fixcrc(Bytes& b) { put32(b,b.size()-12,crc32(b.data()+12,b.size()-24)); }
int main(int argc,char** argv) {
    if(argc!=2) return 2;
    auto imu=load(std::string(argv[1])+"/imu.bin");
    auto cloud=load(std::string(argv[1])+"/cloud.bin");
    auto unknown=load(std::string(argv[1])+"/unknown.bin");
    check(imu.size()==80 && cloud.size()==1044,"wire sizes");
    check(crc32(reinterpret_cast<const uint8_t*>("123456789"),9)==0xcbf43926,"CRC golden");
    for(size_t split=1;split<imu.size();++split) {
        FrameAssembler a;
        check(a.feed(imu.data(),split).empty(),"incomplete frame");
        auto f=a.feed(imu.data()+split,imu.size()-split);
        check(f.size()==1 && f[0]==imu,"all splits recover");
    }
    FrameAssembler a;
    check(a.feed(nullptr,0).empty(),"empty stream");
    Bytes both={0,17,85}; both.insert(both.end(),imu.begin(),imu.end());
    both.insert(both.end(),cloud.begin(),cloud.end());
    check(a.feed(both.data(),both.size()).size()==2,"garbage and concatenation");
    check(a.framing_errors>0,"garbage counted");
    for(int mode=0;mode<4;++mode) {
        FrameAssembler r; auto bad=imu;
        if(mode==0) bad[30]^=1;
        if(mode==1) put32(bad,8,0xffffffff);
        if(mode==2) bad.back()=0;
        if(mode==3) put32(bad,8,24); // known type cannot lie about bounded length
        bad.insert(bad.end(),imu.begin(),imu.end());
        check(r.feed(bad.data(),bad.size()).size()==1,"corruption recovery");
        check(r.crc_errors+r.framing_errors>0,"corruption reported");
    }
    auto d=decode(imu);
    check(d.imu.has_value() && d.sequence==7,"IMU semantics");
    check(d.imu->quaternion[0]==1 && d.imu->angular_velocity[2]==3 &&
          d.imu->linear_acceleration[2]==6,"IMU values");
    check(std::abs(*d.raw_timestamp-10.25)<1e-9,"raw stamp");
    auto c=decode(cloud);
    check(c.cloud && c.cloud->points.size()==2,"cloud count");
    auto p=c.cloud->points[0];
    check(std::abs(p.x-.2)<1e-6 && std::abs(p.y-1)<1e-6 && std::abs(p.z-.1)<1e-6,"calibrated XYZ");
    check(p.intensity==42 && p.ring==1 && std::abs(c.cloud->points[1].time-.0001)<1e-8,"point metadata");
    auto bad=cloud; put32(bad,128,301); fixcrc(bad);
    check(!decode(bad).valid,"point bound");
    bad=imu; put32(bad,24,1000000000); fixcrc(bad);
    check(!decode(bad).valid,"invalid nanoseconds");
    bad=imu; put32(bad,28,0x7fc00000); fixcrc(bad);
    check(decode(bad).imu->nonfinite==1,"NaN retained and counted");
    check(decode(unknown).valid && !decode(unknown).known,"unknown nonfatal");
    check(!decode(Bytes(4)).valid,"short decode safe");
    TimestampAnalyzer t(2,1);
    check(!t.delta() && !t.ratio(),"empty timestamps null");
    t.add(10,100); check(!t.delta() && !t.ratio(),"one sample ratio null");
    t.add(15,110);
    check(*t.delta()==5 && *t.ratio()==.5 && *t.corrected_last==20,"scale without raw overwrite");
    t.add(14,111); check(t.backsteps==1 && !t.ratio(),"backstep invalidates ratio");
    bool rejected=false; try {TimestampAnalyzer badscale(1,0);} catch(const std::exception&) {rejected=true;}
    check(rejected,"zero denominator rejected");
    SequenceStats seq;
    for(auto v:{1022u,1023u,0u,2u,2u,1u}) seq.add(v);
    check(seq.wraps==1 && seq.duplicates==1 && seq.forward_gaps==1 && seq.missing==1 && seq.backward==1,"sequence continuity");
    std::cout<<checks<<" C++ assertions PASS\n";
}
