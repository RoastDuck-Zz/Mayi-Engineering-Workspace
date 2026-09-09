#include <arpa/inet.h>
#include <chrono>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <iostream>
#include <netinet/in.h>
#include <stdexcept>
#include <string>
#include <sys/socket.h>
#include <unistd.h>

static double now(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static uint64_t positive(const char* s){size_t n=0;auto v=std::stoull(s,&n);if(n!=std::strlen(s)||!v)throw std::invalid_argument("positive integer required");return v;}
static void put32(unsigned char* p,uint32_t v){for(int i=0;i<4;++i)p[i]=static_cast<unsigned char>(v>>(8*i));}
int main(int argc,char**argv){
    std::string host="192.168.1.2",output;uint16_t port=6201;uint64_t seconds=5,limit=16*1024*1024;
    try{for(int i=1;i<argc;++i){std::string k=argv[i];if(i+1>=argc)throw std::invalid_argument("missing value");const char*v=argv[++i];if(k=="--host-ip")host=v;else if(k=="--host-port")port=static_cast<uint16_t>(positive(v));else if(k=="--seconds")seconds=positive(v);else if(k=="--output")output=v;else if(k=="--max-bytes")limit=positive(v);else throw std::invalid_argument("unknown option");}if(output.empty()||seconds>10||limit>16*1024*1024)throw std::invalid_argument("output/limit invalid");}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}
    int fd=socket(AF_INET,SOCK_DGRAM|SOCK_CLOEXEC,0);if(fd<0)return 1;int req=4*1024*1024;setsockopt(fd,SOL_SOCKET,SO_RCVBUF,&req,sizeof(req));sockaddr_in addr{};addr.sin_family=AF_INET;addr.sin_port=htons(port);if(inet_pton(AF_INET,host.c_str(),&addr.sin_addr)!=1||bind(fd,reinterpret_cast<sockaddr*>(&addr),sizeof(addr))<0){close(fd);return 1;}
    int file=::open(output.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);if(file<0){close(fd);return 1;}FILE*out=fdopen(file,"wb");if(!out){close(file);close(fd);return 1;}
    const unsigned char header[8]={'G','D','L','2','U','D','P','1'};fwrite(header,1,8,out);uint64_t bytes=8,start_ns=static_cast<uint64_t>(now()*1e9);uint8_t data[65536];int result=0;
    while(now()-start_ns/1e9<seconds){sockaddr_in peer{};iovec iov{data,sizeof(data)};msghdr msg{};msg.msg_name=&peer;msg.msg_namelen=sizeof(peer);msg.msg_iov=&iov;msg.msg_iovlen=1;timeval tv{1,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&tv,sizeof(tv));ssize_t n=recvmsg(fd,&msg,0);if(n<0){if(errno==EAGAIN||errno==EWOULDBLOCK||errno==EINTR)continue;result=1;break;}uint64_t need=8+2+4+4+static_cast<uint64_t>(n);if(bytes+need>limit)break;unsigned char rec[18];uint64_t t=static_cast<uint64_t>(now()*1e9);for(int i=0;i<8;++i)rec[i]=static_cast<unsigned char>(t>>(8*i));rec[8]=static_cast<unsigned char>(ntohs(peer.sin_port));rec[9]=static_cast<unsigned char>(ntohs(peer.sin_port)>>8);std::memcpy(rec+10,&peer.sin_addr.s_addr,4);put32(rec+14,static_cast<uint32_t>(n));fwrite(rec,1,18,out);fwrite(data,1,n,out);bytes+=need;}
    fclose(out);close(fd);std::cout<<"{\"bytes\":"<<bytes<<",\"exit_code\":"<<result<<"}\n";return result;
}
