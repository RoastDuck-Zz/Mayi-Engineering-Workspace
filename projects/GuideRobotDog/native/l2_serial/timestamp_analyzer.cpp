#include "timestamp_analyzer.h"
#include <cmath>
#include <stdexcept>
namespace guidedog::l2 {
TimestampAnalyzer::TimestampAnalyzer(double n,double d):scale_(n/d) {
    if(!std::isfinite(n)||!std::isfinite(d)||n<=0||d<=0||!std::isfinite(scale_)||scale_<=0)
        throw std::invalid_argument("time scale must be positive and finite");
}
void TimestampAnalyzer::add(double raw,double host) {
    if(!std::isfinite(raw)||!std::isfinite(host)) {++invalid;return;}
    if(!count) {first_raw=raw;first_host=host;corrected_first=raw;}
    else if(raw<*last_raw || host<*last_host) ++backsteps;
    last_raw=raw;last_host=host;
    // Preserve the first raw epoch; scale elapsed time only, not the epoch.
    corrected_last=*first_raw+(raw-*first_raw)*scale_; ++count;
}
std::optional<double> TimestampAnalyzer::delta() const {
    if(count<2) return {};
    return *last_raw-*first_raw;
}
std::optional<double> TimestampAnalyzer::host_elapsed() const {
    if(count<2) return {};
    return *last_host-*first_host;
}
std::optional<double> TimestampAnalyzer::ratio() const {
    auto h=host_elapsed();
    if(!h || *h<=0 || backsteps || invalid) return {};
    return *delta()/ *h;
}
}
