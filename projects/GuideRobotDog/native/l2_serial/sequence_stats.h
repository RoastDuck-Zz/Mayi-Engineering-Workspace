#pragma once
#include <cstdint>
#include <optional>
#include <ostream>
namespace guidedog::l2 {
struct SequenceStats {
    std::optional<uint32_t> first,last;
    uint64_t frames=0,duplicates=0,forward_gaps=0,missing=0,backward=0,wraps=0,out_of_range=0;
    uint64_t immediate_gap_events=0,late_packet_count=0,reorder_events=0;
    uint64_t unrecovered_missing_after_window=0;
    static constexpr uint32_t modulus=1024;
    void add(uint32_t value) {
        if(!first) first=value;
        if(value>=1024) ++out_of_range;
        if(last) {
            if(value==*last) ++duplicates;
            else if(value<modulus && *last<modulus) {
                const uint32_t delta=(value-*last+modulus)%modulus;
                if(delta==1) {
                    if(*last==modulus-1 && value==0) ++wraps;
                } else if(delta<=modulus/2) {
                    ++forward_gaps; ++immediate_gap_events; missing+=delta-1;
                } else {
                    ++backward; ++late_packet_count; ++reorder_events;
                }
            } else if(value<*last) { ++backward; ++late_packet_count; ++reorder_events; }
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
        o<<",\"immediate_gap_events\":"<<immediate_gap_events<<",\"late_packet_count\":"<<late_packet_count;
        o<<",\"reorder_events\":"<<reorder_events<<",\"unrecovered_missing_after_window\":"<<unrecovered_missing_after_window;
        o<<",\"sequence_gap_observed\":"<<((forward_gaps||backward)?"true":"false");
        o<<",\"confirmed_packet_loss\":\"UNKNOWN\"}";
    }
};
}
