#include "frame_assembler.h"
#include <algorithm>
namespace guidedog::l2 {
uint32_t le32(const uint8_t* p) {
    return uint32_t(p[0]) | uint32_t(p[1])<<8 | uint32_t(p[2])<<16 | uint32_t(p[3])<<24;
}
// CRC-32/ISO-HDLC, same polynomial and initialization as Unitree BSD utilities.
uint32_t crc32(const uint8_t* p, size_t size) {
    uint32_t c=0xffffffffu;
    for(size_t n=0;n<size;++n) {
        c ^= p[n];
        for(int bit=0;bit<8;++bit) c=(c>>1) ^ ((c&1)?0xedb88320u:0u);
    }
    return ~c;
}
size_t expected_size(uint32_t type) {
    switch(type) {
        case 100:return 32; case 101:return 40; case 102:return 1044;
        case 103:return 5536; case 104:return 80; case 105:return 104;
        case 106:return 32; case 107:return 28; case 108:return 44;
        case 109:return 32; default:return 0;
    }
}
void FrameAssembler::extract(std::vector<Bytes>& out) {
    static const uint8_t magic[]={0x55,0xaa,5,10};
    size_t cursor=0;
    while(buffer_.size()-cursor>=4) {
        auto first=buffer_.begin()+static_cast<ptrdiff_t>(cursor);
        auto found=std::search(first,buffer_.end(),std::begin(magic),std::end(magic));
        size_t pos=static_cast<size_t>(found-buffer_.begin());
        if(found==buffer_.end()) pos=buffer_.size()-3; // retain partial header
        if(pos>cursor) { discarded_bytes+=pos-cursor; ++framing_errors; cursor=pos; }
        if(buffer_.size()-cursor<12) break;
        const auto* p=buffer_.data()+cursor;
        size_t len=le32(p+8), fixed=expected_size(le32(p+4));
        if(len<24 || len>max_frame || (fixed && len!=fixed)) {
            ++framing_errors; ++discarded_bytes; ++cursor; continue;
        }
        if(buffer_.size()-cursor<len) break;
        if(p[len-2]!=0 || p[len-1]!=0xff) {
            ++framing_errors; ++discarded_bytes; ++cursor; continue;
        }
        if(crc32(p+12,len-24)!=le32(p+len-12)) {
            ++crc_errors; ++discarded_bytes; ++cursor; continue;
        }
        out.emplace_back(p,p+len); cursor+=len;
    }
    buffer_.erase(buffer_.begin(),buffer_.begin()+static_cast<ptrdiff_t>(cursor));
}
std::vector<Bytes> FrameAssembler::feed(const uint8_t* data,size_t size) {
    std::vector<Bytes> out;
    // Chunk the caller's input too: retained byte storage is bounded independent
    // of read size. Output ownership belongs to the caller.
    while(size) {
        size_t n=std::min(size,size_t(4096));
        buffer_.insert(buffer_.end(),data,data+n); data+=n; size-=n;
        extract(out);
    }
    return out;
}
}
