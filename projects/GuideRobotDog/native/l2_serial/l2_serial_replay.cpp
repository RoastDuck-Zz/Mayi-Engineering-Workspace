#include "diagnostic_report.h"
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <sstream>
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>
using namespace guidedog::l2;
int main(int argc,char**argv) {
    std::string input,output;
    try {
        for(int i=1;i<argc;++i) {
            std::string key=argv[i];if(i+1>=argc)throw std::invalid_argument("missing value");
            std::string value=argv[++i];
            if(key=="--input")input=value;else if(key=="--output")output=value;
            else throw std::invalid_argument("unknown option");
        }
        if(input.empty()||output.empty()||input==output)throw std::invalid_argument("distinct input/output required");
        std::ifstream in(input,std::ios::binary|std::ios::ate);if(!in)throw std::runtime_error("input unavailable");
        auto size=in.tellg();if(size<0||size>16*1024*1024)throw std::runtime_error("capture limit is 16 MiB");in.seekg(0);
        FrameAssembler assembler;DiagnosticReport report(1,1);report.replay=true;
        char bytes[8192];
        while(in.read(bytes,sizeof(bytes)) || in.gcount()) {
            size_t n=static_cast<size_t>(in.gcount());
            if(report.bytes+n>16*1024*1024)throw std::runtime_error("capture grew beyond 16 MiB");
            report.bytes+=n;
            for(const auto& f:assembler.feed(reinterpret_cast<uint8_t*>(bytes),n))report.observe(decode(f),0);
        }
        if(in.bad())throw std::runtime_error("capture read failed");
        std::ostringstream out;
        report.json(out,"OFFLINE",4000000,std::numeric_limits<double>::quiet_NaN(),assembler,"OFFLINE_REPLAY","",true,1,1);
        const std::string text=out.str();
        int fd=::open(output.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC,0600);
        if(fd<0)throw std::runtime_error("output must be a new file");
        FILE* file=::fdopen(fd,"wb");
        if(!file){::close(fd);throw std::runtime_error("output unavailable");}
        bool ok=std::fwrite(text.data(),1,text.size(),file)==text.size();
        if(std::fclose(file)!=0)ok=false;
        if(!ok)throw std::runtime_error("output failed");
        return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
