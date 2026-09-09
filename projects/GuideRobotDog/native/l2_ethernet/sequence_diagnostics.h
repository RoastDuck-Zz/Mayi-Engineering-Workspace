#pragma once
#include "../l2_serial/sequence_stats.h"
#include "../l2_serial/sequence_window.h"
#include <algorithm>
#include <iomanip>
#include <optional>
#include <ostream>
#include <vector>
namespace guidedog::l2::ethernet {
struct GapObservation {
    uint32_t previous=0,current=0,mod_delta=0;
    double previous_raw=0,current_raw=0,raw_delta=0,previous_host=0,current_host=0,host_delta=0;
    std::optional<float> packet_lost_up_before,packet_lost_up_after,packet_lost_down_before,packet_lost_down_after;
    std::optional<bool> time_span_consistent;
};
struct SequenceTimestampDiagnostics {
    SequenceStats sequence;
    SequenceWindow reorder;
    std::vector<double> raw_periods,host_periods;
    std::vector<GapObservation> gaps;
    std::optional<uint32_t> previous_seq;
    std::optional<double> previous_raw,previous_host;
    std::optional<float> previous_up,previous_down;
    uint64_t packet_state_changed=0;
    std::vector<float> up_values,down_values;
    static double percentile(std::vector<double> values,double fraction) {
        if(values.empty()) return 0;
        std::sort(values.begin(),values.end());
        const double index=fraction*double(values.size()-1);
        const size_t low=static_cast<size_t>(index),high=std::min(low+1,values.size()-1);
        return values[low]+(values[high]-values[low])*(index-double(low));
    }
    void add(uint32_t seq,double raw,double host,std::optional<float> up={},std::optional<float> down={}) {
        if(previous_seq && previous_raw && previous_host) {
            const uint32_t delta=(seq-*previous_seq)%SequenceStats::modulus;
            const double raw_delta=raw-*previous_raw,host_delta=host-*previous_host;
            if(delta==1 && raw_delta>=0 && host_delta>=0) {
                raw_periods.push_back(raw_delta);host_periods.push_back(host_delta);
            } else if(delta!=0) {
                std::optional<bool> consistent;
                if(raw_periods.size()>=30 && delta<=SequenceStats::modulus/2 && raw_delta>0) {
                    const double expected=double(delta)*percentile(raw_periods,.5);
                    if(expected>0) consistent=(raw_delta/expected>=.80 && raw_delta/expected<=1.20);
                }
                gaps.push_back({*previous_seq,seq,delta,*previous_raw,raw,raw_delta,*previous_host,host,host_delta,
                    previous_up,up,previous_down,down,consistent});
            }
        }
        if(up) { up_values.push_back(*up); if(previous_up && *previous_up!=*up) ++packet_state_changed; }
        if(down) { down_values.push_back(*down); if(previous_down && *previous_down!=*down) ++packet_state_changed; }
        sequence.add(seq);reorder.add(seq);previous_seq=seq;previous_raw=raw;previous_host=host;previous_up=up;previous_down=down;
    }
    void json(std::ostream& o) const {
        o<<"{\"sequence\":";sequence.json(o);
        o<<",\"immediate_gap_events\":"<<reorder.immediate_gap_events()
         <<",\"late_packet_count\":"<<reorder.late_packet_count()
         <<",\"reorder_events\":"<<reorder.reorder_events()
         <<",\"unrecovered_missing_after_window\":"<<reorder.unrecovered_missing();
        const double missing=double(reorder.unrecovered_missing());
        o<<",\"missing_fraction\":"<<(sequence.frames+missing>0?missing/(double(sequence.frames)+missing):0);
        o<<",\"nominal_period\":{";
        auto emit=[&o](const char* n,const std::vector<double>& values) {
            o<<'"'<<n<<"\":{\"count\":"<<values.size();
            if(values.empty()) {o<<",\"min\":null,\"median\":null,\"p50\":null,\"p95\":null,\"max\":null}";return;}
            auto copy=values;
            auto min=*std::min_element(copy.begin(),copy.end());
            auto max=*std::max_element(copy.begin(),copy.end());
            o<<",\"min\":"<<std::setprecision(17)<<min<<",\"median\":"<<percentile(copy,.5)
             <<",\"p50\":"<<percentile(copy,.5)<<",\"p95\":"<<percentile(copy,.95)<<",\"max\":"<<max<<'}';
        };
        emit("raw_device_seconds",raw_periods);o<<',';emit("host_seconds",host_periods);o<<'}';
        o<<",\"packet_state_changed_count\":"<<packet_state_changed;
        o<<",\"packet_lost_up_samples\":"<<up_values.size()<<",\"packet_lost_down_samples\":"<<down_values.size();
        o<<",\"gap_observations\":[";
        for(size_t i=0;i<gaps.size() && i<64;++i) {
            if(i)o<<',';
            const auto& g=gaps[i];
            o<<"{\"previous_seq\":"<<g.previous<<",\"current_seq\":"<<g.current<<",\"mod_delta\":"<<g.mod_delta
             <<",\"raw_timestamp_delta\":"<<g.raw_delta<<",\"host_delta\":"<<g.host_delta
             <<",\"packet_lost_up_before\":"<<(g.packet_lost_up_before?std::to_string(*g.packet_lost_up_before):"null")
             <<",\"packet_lost_up_after\":"<<(g.packet_lost_up_after?std::to_string(*g.packet_lost_up_after):"null")
             <<",\"packet_lost_down_before\":"<<(g.packet_lost_down_before?std::to_string(*g.packet_lost_down_before):"null")
             <<",\"packet_lost_down_after\":"<<(g.packet_lost_down_after?std::to_string(*g.packet_lost_down_after):"null")
             <<",\"time_span_consistent\":"<<(g.time_span_consistent?(*g.time_span_consistent?"true":"false"):"null")<<'}';
        }
        o<<']'<<'}';
    }
};
}
