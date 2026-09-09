#include "serial_transport.h"
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <poll.h>
#include <stdexcept>
#include <sys/stat.h>
#include <termios.h>
#include <unistd.h>
namespace guidedog::l2 {
static std::runtime_error failure(const char* operation) {
    return std::runtime_error(std::string(operation)+": "+std::strerror(errno));
}
SerialTransport::SerialTransport(const std::string& device,unsigned baudrate) {
    if(baudrate!=4000000) throw std::invalid_argument("unsupported baudrate: expected 4000000");
#ifndef B4000000
    throw std::runtime_error("unsupported platform: termios B4000000 unavailable");
#else
    fd_=::open(device.c_str(),O_RDONLY|O_NOCTTY|O_NONBLOCK|O_CLOEXEC);
    if(fd_<0) {
        if(errno==ENOENT || errno==ENOTDIR)
            throw std::runtime_error("persistent L2 device not found; run scripts/l2_serial_discover.sh first");
        throw failure("serial open");
    }
    try {
        struct stat st{};
        if(fstat(fd_,&st)!=0) throw failure("serial fstat");
        if(!S_ISCHR(st.st_mode)) throw std::runtime_error("serial device is not a character device");
        termios settings{};
        if(tcgetattr(fd_,&settings)!=0) throw failure("serial tcgetattr");
        cfmakeraw(&settings);
        settings.c_iflag &= ~(IXON|IXOFF|IXANY);
        settings.c_cflag &= ~(CSIZE|PARENB|CSTOPB|CRTSCTS|HUPCL);
        settings.c_cflag |= CS8|CLOCAL|CREAD;
        settings.c_cc[VMIN]=0; settings.c_cc[VTIME]=0;
        if(cfsetispeed(&settings,B4000000)!=0 || cfsetospeed(&settings,B4000000)!=0)
            throw failure("serial baudrate");
        if(tcsetattr(fd_,TCSANOW,&settings)!=0) throw failure("serial tcsetattr");
        termios actual{};
        if(tcgetattr(fd_,&actual)!=0) throw failure("serial readback");
        if(cfgetispeed(&actual)!=B4000000 || cfgetospeed(&actual)!=B4000000 ||
           (actual.c_cflag&CSIZE)!=CS8 || (actual.c_cflag&(PARENB|CSTOPB|CRTSCTS|HUPCL)) ||
           (actual.c_iflag&(IXON|IXOFF|IXANY)) || (actual.c_lflag&(ICANON|ECHO|ISIG)))
            throw std::runtime_error("serial 4000000 raw 8N1 configuration unsupported");
        // Discard host-side input queued while no monitor was running. Otherwise
        // stale device stamps are paired with this run's receive time. TCIFLUSH
        // discards input only; it emits no bytes or clock/configuration command.
        if(tcflush(fd_,TCIFLUSH)!=0) throw failure("serial discard stale input");
    } catch(...) {close();throw;}
#endif
}
SerialTransport::~SerialTransport() {close();}
bool SerialTransport::close() {
    if(fd_<0) return true;
    int fd=fd_;fd_=-1;
    // Linux closes the fd even on EINTR; never retry a potentially reused fd.
    return ::close(fd)==0;
}
size_t SerialTransport::receive(uint8_t* data,size_t capacity,int timeout_ms) {
    pollfd item{fd_,POLLIN,0};
    int ready=::poll(&item,1,timeout_ms);
    if(ready<0) {if(errno==EINTR) return 0;throw failure("serial poll");}
    if(!ready) return 0;
    if(item.revents&(POLLERR|POLLHUP|POLLNVAL)) throw std::runtime_error("serial disconnected or poll error");
    if(!(item.revents&POLLIN)) return 0;
    ssize_t count=::read(fd_,data,capacity);
    if(count<0) {
        if(errno==EAGAIN || errno==EWOULDBLOCK || errno==EINTR) return 0;
        throw failure("serial read");
    }
    return static_cast<size_t>(count);
}
}
