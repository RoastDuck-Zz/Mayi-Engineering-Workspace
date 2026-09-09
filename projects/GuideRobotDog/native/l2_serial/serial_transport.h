#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
namespace guidedog::l2 {
// Receive-only descriptor: deliberately has no transmit or modem-control API.
class SerialTransport {
public:
    SerialTransport(const std::string& device, unsigned baudrate);
    ~SerialTransport();
    SerialTransport(const SerialTransport&)=delete;
    SerialTransport& operator=(const SerialTransport&)=delete;
    size_t receive(uint8_t* data,size_t capacity,int timeout_ms);
    bool close();
private:
    int fd_=-1;
};
}
