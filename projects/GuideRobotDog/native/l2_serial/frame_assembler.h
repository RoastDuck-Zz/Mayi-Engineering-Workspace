#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>
namespace guidedog::l2 {
using Bytes = std::vector<uint8_t>;
uint32_t le32(const uint8_t* p);
uint32_t crc32(const uint8_t* p, size_t size);
// Known fixed sizes come from the pinned protocol's fields, not stale comments.
size_t expected_size(uint32_t type);
class FrameAssembler {
public:
    static constexpr size_t max_frame=65536;
    std::vector<Bytes> feed(const uint8_t* data, size_t size);
    size_t pending() const { return buffer_.size(); }
    uint64_t crc_errors=0, framing_errors=0, discarded_bytes=0;
private:
    Bytes buffer_;
    void extract(std::vector<Bytes>& out);
};
}
