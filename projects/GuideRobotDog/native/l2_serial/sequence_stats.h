#pragma once
#include <cstdint>
#include <optional>
#include <ostream>
namespace guidedog::l2 {
struct SequenceStats {
    std::optional<uint32_t> first,last;
    uint64_t frames=0,duplicates=0,forward_gaps=0,missing=0,backward=0,wraps=0,out_of_range=0;
    void add(uint32_t value) {
        if(!first) first=value;
        if(value>=1024) ++out_of_range;
        if(last) {
            if(value==*last) ++duplicates;
            else if(*last==1023 && value==0) ++wraps;
            else if(value>*last && value<1024 && *last<1024) {
                if(value!=*last+1) {++forward_gaps;missing+=value-*last-1;}
            } else if(value<*last) ++backward;
        }
        ++frames;last=value;
    }
    void json(std::ostream& o) const {
        o<<"{\"first_seq\":";if(first)o<<*first;else o<<"null";
        o<<",\"last_seq\":";if(last)o<<*last;else o<<"null";
        o<<",\"frames\":"<<frames<<",\"expected_next\":";
        if(last && *last<1024)o<<((*last+1)%1024);else o<<"null";
        o<<",\"duplicates\":"<<duplicates<<",\"forward_gaps\":"<<forward_gaps;
        o<<",\"estimated_missing_between_valid_frames\":"<<missing;
        o<<",\"backward_unexpected\":"<<backward<<",\"wraps\":"<<wraps<<",\"out_of_range\":"<<out_of_range;
        o<<",\"sequence_gap_observed\":"<<((forward_gaps||backward)?"true":"false");
        o<<",\"confirmed_packet_loss\":\"UNKNOWN\"}";
    }
};
}
