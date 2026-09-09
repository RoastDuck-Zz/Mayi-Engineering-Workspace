#pragma once

#include "../l2_serial/sequence_stats.h"
#include "../l2_serial/sequence_window.h"
#include <algorithm>
#include <cmath>
#include <iomanip>
#include <optional>
#include <ostream>
#include <vector>

namespace guidedog::l2::ethernet {
struct GapObservation {
    uint32_t previous=0,current=0,mod_delta=0;
    double previous_raw=0,current_raw=0,raw_delta=0,previous_host=0,current_host=0,host_delta=0;
    bool missing_likely=false;
};

struct SequenceTimestampDiagnostics {
    SequenceStats sequence;
    SequenceWindow reorder;
    std::vector<double> raw_periods,host_periods;
    std::vector<GapObservation> gaps;
    std::optional<uint32_t> previous_seq;
    std::optional<double> previous_raw,previous_host;
    static double percentile(std::vector<double> values,double fraction) {
        if(values.empty()) return 0;
        std::sort(values.begin(),values.end());
        const double index=fraction*double(values.size()-1);
        const size_t low=static_cast<size_t>(index),high=std::min(low+1,values.size()-1);
        return values[low]+(values[high]-values[low])*(index-double(low));
    }
    void add(uint32_t seq,double raw,double host) {
        if(previous_seq && previous_raw && previous_host) {
            const uint32_t delta=(seq-*previous_seq)%SequenceStats::modulus;
            const double raw_delta=raw-*previous_raw,host_delta=host-*previous_host;
            if(delta==1 && raw_delta>=0 && host_delta>=0) {raw_periods.push_back(raw_delta);host_periods.push_back(host_delta);}
            else if(delta!=0) gaps.push_back({*previous_seq,seq,delta,*previous_raw,raw,raw_delta,*previous_host,host,host_delta,
                delta<=SequenceStats::modulus/2 && raw_delta>0});
        }
        sequence.add(seq);reorder.add(seq);previous_seq=seq;previous_raw=raw;previous_host=host;
    }
    void json(std::ostream& o) const {
        o<<"{\"sequence\":";sequence.json(o);
        o<<",\"immediate_gap_events\":"<<reorder.immediate_gap_events()
         <<",\"late_packet_count\":"<<reorder.late_packet_count()
         <<",\"reorder_events\":"<<reorder.reorder_events()
         <<",\"unrecovered_missing_after_window\":"<<reorder.unrecovered_missing();
        o<<",\"nominal_period\":{";
        auto emit=[&o](const char* n,const std::vector<double>& values) {
            o<<'"'<<n<<"\":{\"count\":"<<values.size();
            if(values.empty()) {o<<",\"min\":null,\"median\":null,\"p50\":null,\"p95\":null,\"max\":null}";return;}
            auto copy=values;auto min=*std::min_element(copy.begin(),copy.end());auto max=*std::max_element(copy.begin(),copy.end());
            o<<",\"min\":"<<std::setprecision(17)<<min<<",\"median\":"<<percentile(copy,.5)
             <<",\"p50\":"<<percentile(copy,.5)<<",\"p95\":"<<percentile(copy,.95)<<",\"max\":"<<max<<'}';
        };
        emit("raw_device_seconds",raw_periods);o<<',';emit("host_seconds",host_periods);o<<'}';
        o<<",\"gap_observations\":[";
        for(size_t i=0;i<gaps.size() && i<64;++i) {if(i)o<<',';const auto& g=gaps[i];o<<"{\"previous_seq\":"<<g.previous<<",\"current_seq\":"<<g.current<<",\"mod_delta\":"<<g.mod_delta<<",\"raw_timestamp_delta\":"<<g.raw_delta<<",\"host_delta\":"<<g.host_delta<<",\"missing_likely\":"<<(g.missing_likely?"true":"false")<<'}';}o<<']';
        o<<'}';
    }
};
}
