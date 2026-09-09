#include "udp_protocol.h"
#include <algorithm>

namespace guidedog::l2::ethernet {
UdpValidation validate_datagram(const uint8_t* data,size_t size,UdpCounters& c) {
    UdpValidation result;
    size_t offset=0;
    while(offset<size) {
        if(size-offset<12 || data[offset]!=0x55 || data[offset+1]!=0xaa ||
           data[offset+2]!=5 || data[offset+3]!=10) {
            ++c.malformed_header; break;
        }
        const uint32_t type=le32(data+offset+4), length=le32(data+offset+8);
        if(length<24 || length>65536 || length>size-offset) {++c.size_mismatch;break;}
        Bytes frame(data+offset,data+offset+length);
        if(frame[length-2]!=0 || frame[length-1]!=0xff) {++c.tail_errors;offset+=length;continue;}
        if(crc32(frame.data()+12,length-24)!=le32(frame.data()+length-12)) {++c.crc_errors;offset+=length;continue;}
        if(type==102) ++c.cloud_frames; else if(type==104) ++c.imu_frames; else ++c.unknown_types;
        result.valid_frames.push_back(std::move(frame)); offset+=length;
    }
    return result;
}
}
