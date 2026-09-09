#include "udp_protocol.h"
#include "sequence_diagnostics.h"
#include "../l2_serial/l2_packet_decoder.h"
#include <arpa/inet.h>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <algorithm>
#include <cerrno>
#include <iostream>
#include <netinet/in.h>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/socket.h>
#include <unistd.h>

using namespace guidedog::l2;
using namespace guidedog::l2::ethernet;
static volatile std::sig_atomic_t stopped=0;
static void stop(int s){stopped=s;}
static double now(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static uint64_t positive(const char* s){size_t n=0;auto v=std::stoull(s,&n);if(n!=std::strlen(s)||!v)throw std::invalid_argument("positive integer required");return v;}
static void json_string(std::ostream& o,const std::string& s){o<<'"';for(char c:s){if(c=='"'||c=='\\')o<<'\\';o<<c;}o<<'"';}
static void usage(){std::cerr<<"usage: l2_udp_monitor [--seconds N] [--host-ip IP] [--lidar-ip IP] [--host-port N] [--lidar-port N] [--output PREFIX] [--rcvbuf-bytes N]\n";}

int main(int argc,char** argv){
    std::string host="192.168.1.2",lidar="192.168.1.62",output;uint16_t host_port=6201,lidar_port=6101;uint64_t seconds=10,requested_rcvbuf=4*1024*1024;
    try {
        for(int i=1;i<argc;++i){std::string k=argv[i];if(i+1>=argc)throw std::invalid_argument("missing value");const char* v=argv[++i];
            if(k=="--seconds")seconds=positive(v);else if(k=="--host-ip")host=v;else if(k=="--lidar-ip")lidar=v;
            else if(k=="--host-port")host_port=static_cast<uint16_t>(positive(v));else if(k=="--lidar-port")lidar_port=static_cast<uint16_t>(positive(v));
            else if(k=="--output")output=v;else if(k=="--rcvbuf-bytes")requested_rcvbuf=positive(v);else{usage();return 2;}}
        if(seconds>120)throw std::invalid_argument("seconds must be <=120");
    } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
    int fd=::socket(AF_INET,SOCK_DGRAM|SOCK_CLOEXEC,0);if(fd<0){perror("socket");return 1;}
    int req=static_cast<int>(std::min<uint64_t>(requested_rcvbuf,0x7fffffff));setsockopt(fd,SOL_SOCKET,SO_RCVBUF,&req,sizeof(req));
    int actual=0;socklen_t actual_len=sizeof(actual);getsockopt(fd,SOL_SOCKET,SO_RCVBUF,&actual,&actual_len);
    int one=1;bool ovfl_supported=setsockopt(fd,SOL_SOCKET,SO_RXQ_OVFL,&one,sizeof(one))==0;
    sockaddr_in bind_addr{};bind_addr.sin_family=AF_INET;bind_addr.sin_port=htons(host_port);if(inet_pton(AF_INET,host.c_str(),&bind_addr.sin_addr)!=1){close(fd);return 2;}
    if(bind(fd,reinterpret_cast<sockaddr*>(&bind_addr),sizeof(bind_addr))<0){perror("bind");close(fd);return 1;}
    signal(SIGINT,stop);signal(SIGTERM,stop);sockaddr_in expected{};expected.sin_family=AF_INET;expected.sin_port=htons(lidar_port);inet_pton(AF_INET,lidar.c_str(),&expected.sin_addr);
    UdpCounters c;SequenceTimestampDiagnostics cloud,imu;std::optional<uint32_t> first_ovfl,last_ovfl;double start=now();
    while(!stopped && now()-start<seconds){
        uint8_t data[65536],control[CMSG_SPACE(sizeof(uint32_t))];iovec iov{data,sizeof(data)};msghdr msg{};sockaddr_in peer{};iov.iov_base=data;iov.iov_len=sizeof(data);msg.msg_name=&peer;msg.msg_namelen=sizeof(peer);msg.msg_iov=&iov;msg.msg_iovlen=1;msg.msg_control=control;msg.msg_controllen=sizeof(control);
        timeval timeout{1,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));ssize_t n=recvmsg(fd,&msg,0);if(n<0){if(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR)continue;perror("recvmsg");break;}
        ++c.datagrams_total;c.bytes_total+=static_cast<uint64_t>(n);uint32_t ovfl=0;bool got_ovfl=false;
        for(cmsghdr* h=CMSG_FIRSTHDR(&msg);h;h=CMSG_NXTHDR(&msg,h))if(h->cmsg_level==SOL_SOCKET&&h->cmsg_type==SO_RXQ_OVFL&&h->cmsg_len>=CMSG_LEN(sizeof(uint32_t))){std::memcpy(&ovfl,CMSG_DATA(h),sizeof(ovfl));got_ovfl=true;}
        if(got_ovfl){if(!first_ovfl)first_ovfl=ovfl;last_ovfl=ovfl;}
        if(peer.sin_addr.s_addr!=expected.sin_addr.s_addr||peer.sin_port!=expected.sin_port){++c.wrong_source;continue;}
        auto validated=validate_datagram(data,static_cast<size_t>(n),c);double host_time=now();
        for(const auto& frame:validated.valid_frames){auto d=decode(frame);if(!d.valid)continue;if(d.cloud)cloud.add(*d.sequence,*d.raw_timestamp,host_time,d.packet_lost_up,d.packet_lost_down);if(d.imu)imu.add(*d.sequence,*d.raw_timestamp,host_time);}
    }
    close(fd);std::ostringstream out;out<<"{\"status\":"<<(stopped?"\"INTERRUPTED\"":"\"OK\"")<<",\"runtime_seconds\":"<<now()-start;
    out<<",\"bind_ip\":";json_string(out,host);out<<",\"source_ip\":";json_string(out,lidar);out<<",\"host_port\":"<<host_port<<",\"lidar_port\":"<<lidar_port;
    out<<",\"requested_rcvbuf\":"<<requested_rcvbuf<<",\"actual_rcvbuf\":"<<actual<<",\"so_rxq_ovfl\":{\"supported\":"<<(ovfl_supported?"true":"false")<<",\"first_counter\":"<<(first_ovfl?std::to_string(*first_ovfl):"null")<<",\"last_counter\":"<<(last_ovfl?std::to_string(*last_ovfl):"null")<<",\"delta\":"<<(first_ovfl&&last_ovfl?std::to_string(*last_ovfl-*first_ovfl):"null")<<"}";
    out<<",\"datagrams_total\":"<<c.datagrams_total<<",\"bytes_total\":"<<c.bytes_total<<",\"wrong_source\":"<<c.wrong_source<<",\"size_mismatch\":"<<c.size_mismatch<<",\"malformed_header\":"<<c.malformed_header<<",\"tail_errors\":"<<c.tail_errors<<",\"crc_errors\":"<<c.crc_errors<<",\"unknown_types\":"<<c.unknown_types<<",\"cloud_frames\":"<<c.cloud_frames<<",\"imu_frames\":"<<c.imu_frames;
    out<<",\"cloud\":";cloud.json(out);out<<",\"imu\":";imu.json(out);out<<'}';
    if(output.empty())std::cout<<out.str()<<'\n';else{std::ofstream f(output+"-summary.json");if(!f)return 1;f<<out.str()<<'\n';}return 0;
}
