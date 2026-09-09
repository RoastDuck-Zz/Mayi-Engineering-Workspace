#include "serial_transport.h"
#include "diagnostic_report.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
using namespace guidedog::l2;
namespace {
volatile std::sig_atomic_t stopped=0;
void on_signal(int n) {stopped=n;}
double monotonic() {
    return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();
}
double positive(const std::string& v) {
    size_t end=0;double x=std::stod(v,&end);
    if(end!=v.size() || !std::isfinite(x) || x<=0) throw std::invalid_argument("expected positive finite number");
    return x;
}
void csv_packet(std::ostream& o,const DecodedPacket& d,double host,const DiagnosticReport& r) {
    o<<"true,"<<d.declared_length<<','<<d.type<<',';
    if(d.sequence) o<<*d.sequence;
    o<<",true,"<<(d.valid?"true":"false")<<',';
    if(d.raw_sec) o<<*d.raw_sec;
    o<<',';if(d.raw_nsec) o<<*d.raw_nsec;
    o<<',';number(o,d.raw_timestamp);o<<',';number(o,host);o<<',';
    number(o,d.cloud?r.cloud_time.corrected_last:(d.imu?r.imu_time.corrected_last:std::nullopt));o<<'\n';
}
}
int main(int argc,char** argv) {
    std::string device="/dev/unitree_l2",output="reports/l2-serial";
    double seconds=60,num=1,den=1;unsigned baud=4000000;
    bool sample=false,frames=false;
    try {
        for(int i=1;i<argc;++i) {
            std::string arg=argv[i];
            if(arg=="--help") {
                std::cout<<"l2_serial_monitor [--device /dev/unitree_l2] [--seconds 60] [--baudrate 4000000]\n"
                           " [--output reports/l2-serial] [--frames-csv] [--sample-cloud-frame]\n"
                           " [--time-scale-num 1] [--time-scale-den 1]\n";return 0;
            }
            if(arg=="--sample-cloud-frame") {sample=true;continue;}
            if(arg=="--frames-csv") {frames=true;continue;}
            if(i+1>=argc) throw std::invalid_argument("missing argument value");
            std::string value=argv[++i];
            if(arg=="--device") device=value;
            else if(arg=="--output") output=value;
            else if(arg=="--seconds") seconds=positive(value);
            else if(arg=="--time-scale-num") num=positive(value);
            else if(arg=="--time-scale-den") den=positive(value);
            else if(arg=="--baudrate") {
                if(positive(value)!=4000000) throw std::invalid_argument("unsupported baudrate; expected 4000000");
            } else throw std::invalid_argument("unknown option: "+arg);
        }
        if(seconds>86400 || device.empty() || output.empty()) throw std::invalid_argument("invalid duration or empty path");
        TimestampAnalyzer validate(num,den);
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 2;}
    DiagnosticReport report(num,den);FrameAssembler assembler;
    std::unique_ptr<SerialTransport> transport;
    std::ofstream frame_csv;
    double start=monotonic();int code=0;
    bool clean=true;std::string status="DATA_RECEIVED",error;
    std::signal(SIGINT,on_signal);std::signal(SIGTERM,on_signal);
    try {
        // Open exactly the requested device; no enumeration or fallback here.
        transport=std::make_unique<SerialTransport>(device,baud);
        auto parent=std::filesystem::path(output).parent_path();
        if(!parent.empty()) std::filesystem::create_directories(parent);
        if(frames) {
            frame_csv.exceptions(std::ios::failbit|std::ios::badbit);
            frame_csv.open(output+"-frames.csv");
            frame_csv<<"header_valid,declared_length,packet_type,sequence,crc_valid,decode_valid,raw_sec,raw_nsec,raw_device_timestamp,host_monotonic_receive_time,corrected_timestamp\n";
        }
        start=monotonic();
        while(!stopped) {
            double remaining=seconds-(monotonic()-start);if(remaining<=0) break;
            uint8_t buffer[8192];
            int timeout=std::max(1,std::min(100,int(std::ceil(remaining*1000))));
            size_t n=transport->receive(buffer,sizeof(buffer),timeout);double host=monotonic();report.bytes+=n;
            for(const auto& f:assembler.feed(buffer,n)) {
                auto d=decode(f);report.observe(d,host);
                if(frames) csv_packet(frame_csv,d,host,report);
                if(sample && d.valid && d.cloud) {
                    std::ofstream out;out.exceptions(std::ios::failbit|std::ios::badbit);
                    out.open(output+"-sample-cloud.csv");out<<"x,y,z,intensity,relative_time,ring\n";
                    for(const auto& p:d.cloud->points) {
                        number(out,p.x);out<<',';number(out,p.y);out<<',';number(out,p.z);out<<',';
                        number(out,p.intensity);out<<',';number(out,p.time);out<<','<<p.ring<<'\n';
                    }
                    out.close();sample=false;
                }
            }
        }
        if(frames) frame_csv.close();
        if(stopped) {code=128+stopped;status="INTERRUPTED";}
        else if(!report.cloud_frames && !report.imu_frames) {
            code=3;status=report.bytes?"NO_SENSOR_DATA":"NO_DATA";
        }
    } catch(const std::exception& e) {code=1;status="ERROR";error=e.what();std::cerr<<error<<'\n';}
    if(transport) clean=transport->close();
    if(!clean) {code=1;status="ERROR";error+=" serial close failed";}
    try {
        auto parent=std::filesystem::path(output).parent_path();
        if(!parent.empty()) std::filesystem::create_directories(parent);
        std::ofstream out;out.exceptions(std::ios::failbit|std::ios::badbit);out.open(output+"-summary.json");
        report.json(out,device,baud,monotonic()-start,assembler,status,error,clean,num,den);out.close();
    } catch(const std::exception& e) {std::cerr<<"report output failed: "<<e.what()<<'\n';return 1;}
    std::cout<<status<<'\n';return code;
}
