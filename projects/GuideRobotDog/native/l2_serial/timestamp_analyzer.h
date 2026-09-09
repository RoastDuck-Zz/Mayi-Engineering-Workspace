#pragma once
#include <cstdint>
#include <optional>
namespace guidedog::l2 {
class TimestampAnalyzer {
public:
    TimestampAnalyzer(double numerator=1,double denominator=1);
    void add(double raw,double host);
    std::optional<double> delta() const;
    std::optional<double> host_elapsed() const;
    std::optional<double> ratio() const;
    std::optional<double> first_raw,last_raw,first_host,last_host,corrected_first,corrected_last;
    uint64_t count=0,backsteps=0,invalid=0;
private:
    double scale_;
};
}
