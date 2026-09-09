#pragma once

#include <cstdint>
#include <deque>
#include <optional>
#include <unordered_map>
#include <unordered_set>

namespace guidedog::l2 {

// Small modulo-1024 reorder window for packet sequence diagnostics. It never
// fabricates a frame and only retires a missing candidate after the window ages.
class SequenceWindow {
public:
    explicit SequenceWindow(uint32_t window = 64):window_(window ? window : 1) {}

    void add(uint32_t value) {
        if(value >= modulus) return;
        age_pending();
        auto found=pending_.find(value);
        if(found != pending_.end()) {
            ++late_packet_count_; ++reorder_events_; pending_.erase(found);
            return;
        }
        if(seen_.find(value) != seen_.end()) { ++duplicates_; return; }
        seen_.insert(value); history_.push_back(value);
        while(history_.size()>window_*2+2) {seen_.erase(history_.front());history_.pop_front();}
        if(!last_) {last_=value;return;}
        const uint32_t delta=(value-*last_+modulus)%modulus;
        if(delta==0) {++duplicates_;return;}
        if(delta<=modulus/2) {
            if(delta>1) {
                ++immediate_gap_events_;
                for(uint32_t i=1;i<delta;++i) pending_.emplace((*last_+i)%modulus,PendingAge{0});
            }
        } else { ++late_packet_count_; ++reorder_events_; }
        last_=value;
    }
    uint64_t immediate_gap_events() const {return immediate_gap_events_;}
    uint64_t late_packet_count() const {return late_packet_count_;}
    uint64_t reorder_events() const {return reorder_events_;}
    uint64_t unrecovered_missing() const {return unrecovered_missing_;}
    uint64_t duplicates() const {return duplicates_;}
private:
    static constexpr uint32_t modulus=1024;
    struct PendingAge {uint32_t age;};
    void age_pending() {
        for(auto it=pending_.begin();it!=pending_.end();) {
            if(++it->second.age > window_) {++unrecovered_missing_;it=pending_.erase(it);} else ++it;
        }
    }
    uint32_t window_;
    std::optional<uint32_t> last_;
    std::unordered_map<uint32_t,PendingAge> pending_;
    std::unordered_set<uint32_t> seen_;
    std::deque<uint32_t> history_;
    uint64_t immediate_gap_events_=0,late_packet_count_=0,reorder_events_=0;
    uint64_t unrecovered_missing_=0,duplicates_=0;
};
}
