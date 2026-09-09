#include "serial_transport.h"
#include "diagnostic_report.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdio>
#include <fcntl.h>
#include <iostream>
#include <stdexcept>
#include <unistd.h>
using namespace guidedog::l2;
static volatile std::sig_atomic_t stopped=0;
static void stop(int n) {stopped=n;}
static double mono() {return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static double positive(const std::string& text) {
    size_t end=0;double n=std::stod(text,&end);
    if(end!=text.size()||!std::isfinite(n)||n<=0)throw std::invalid_argument("positive finite value required");
    return n;
}
int main(int argc,char**argv) {
    std::string device="/dev/unitree_l2",output;double seconds=5;size_t limit=16*1024*1024;
    try {
        for(int i=1;i<argc;++i) {
            std::string key=argv[i];if(i+1>=argc)throw std::invalid_argument("missing value");
            std::string value=argv[++i];
            if(key=="--device")device=value;
            else if(key=="--output")output=value;
            else if(key=="--seconds")seconds=positive(value);
            else if(key=="--max-bytes") {
                double n=positive(value);
                if(n>16*1024*1024||std::floor(n)!=n)throw std::invalid_argument("maximum capture is 16 MiB");
                limit=static_cast<size_t>(n);
            } else throw std::invalid_argument("unknown option");
        }
        if(output.empty()||seconds>10)throw std::invalid_argument("output required; seconds at most 10");
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 2;}
    // Output descriptor is exclusively a newly created local evidence file.
    int file_fd=::open(output.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
    if(file_fd<0){std::cerr<<"cannot exclusively create private capture\n";return 1;}
    FILE* out=fdopen(file_fd,"wb");
    if(!out){::close(file_fd);return 1;}
    std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
    size_t bytes=0;double start=mono();int result=0;
    try {
        SerialTransport transport(device,4000000);start=mono();
        while(!stopped && bytes<limit) {
            double remaining=seconds-(mono()-start);if(remaining<=0)break;
            uint8_t data[8192];
            size_t n=transport.receive(data,std::min(sizeof(data),limit-bytes),std::min(100,int(std::ceil(remaining*1000))));
            if(n && fwrite(data,1,n,out)!=n)throw std::runtime_error("capture file output failed");
            bytes+=n;
        }
        if(!transport.close())throw std::runtime_error("serial close failed");
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';result=1;}
    if(fclose(out)!=0)result=1;
    if(stopped)result=128+stopped;
    std::cout<<"{\"bytes\":"<<bytes<<",\"runtime_seconds\":";number(std::cout,mono()-start);
    std::cout<<",\"byte_limit_reached\":"<<(bytes==limit?"true":"false")<<",\"exit_code\":"<<result<<"}\n";
    return result;
}
