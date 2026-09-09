#include "udp_protocol.h"
#include "sequence_diagnostics.h"
#include "../l2_serial/l2_packet_decoder.h"
#include <cstdint>
#include <fstream>
#include <fcntl.h>
#include <unistd.h>
#include <cstdio>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

using namespace guidedog::l2;using namespace guidedog::l2::ethernet;
static uint32_t get32(const unsigned char*p){return uint32_t(p[0])|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;}
static uint64_t get64(const unsigned char*p){uint64_t v=0;for(int i=7;i>=0;--i)v=(v<<8)|p[i];return v;}
int main(int argc,char**argv){std::string input,output;for(int i=1;i<argc;++i){std::string k=argv[i];if(i+1>=argc)return 2;std::string v=argv[++i];if(k=="--input")input=v;else if(k=="--output")output=v;else return 2;}if(input.empty()||output.empty()||input==output)return 2;
    std::ifstream in(input,std::ios::binary|std::ios::ate);if(!in)return 1;auto sz=in.tellg();if(sz<8||sz>16*1024*1024)return 1;in.seekg(0);unsigned char magic[8];in.read(reinterpret_cast<char*>(magic),8);if(std::string(reinterpret_cast<char*>(magic),8)!="GDL2UDP1")return 1;
    UdpCounters c;SequenceTimestampDiagnostics cloud,imu;uint64_t bytes=8;unsigned char rec[18];
    while(in.read(reinterpret_cast<char*>(rec),18)){uint64_t t=get64(rec);uint32_t n=get32(rec+14);if(n>65536||bytes+18+n>16*1024*1024)return 1;std::vector<uint8_t> data(n);in.read(reinterpret_cast<char*>(data.data()),n);if(!in)return 1;bytes+=18+n;++c.datagrams_total;c.bytes_total+=n;auto valid=validate_datagram(data.data(),n,c);double host=double(t)/1e9;for(const auto& frame:valid.valid_frames){auto d=decode(frame);if(!d.valid)continue;if(d.cloud)cloud.add(*d.sequence,*d.raw_timestamp,host);if(d.imu)imu.add(*d.sequence,*d.raw_timestamp,host);}}
    std::ostringstream out;out<<"{\"bytes\":"<<bytes<<",\"datagrams_total\":"<<c.datagrams_total<<",\"crc_errors\":"<<c.crc_errors<<",\"tail_errors\":"<<c.tail_errors<<",\"malformed_header\":"<<c.malformed_header<<",\"size_mismatch\":"<<c.size_mismatch<<",\"cloud_frames\":"<<c.cloud_frames<<",\"imu_frames\":"<<c.imu_frames<<",\"cloud\":";cloud.json(out);out<<",\"imu\":";imu.json(out);out<<'}';
    const std::string text=out.str()+"\n";int fd=::open(output.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);if(fd<0)return 1;FILE* f=fdopen(fd,"wb");if(!f){close(fd);return 1;}bool ok=fwrite(text.data(),1,text.size(),f)==text.size();if(fclose(f)!=0)ok=false;return ok?0:1;
}
