// Cloud geometry adapted from Unitree Robotics (c) 2020-2024 BSD-3-Clause
// parseFromPacketToPointCloud, pinned v2.0.10. See UNITREE-LICENSE.txt.
#include "l2_packet_decoder.h"
#include <cmath>
#include <cstring>
#include <limits>
namespace guidedog::l2 {
static double f32(const uint8_t* p) {
    static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559);
    uint32_t bits=le32(p); float f; std::memcpy(&f,&bits,4); return f;
}
DecodedPacket decode(const Bytes& b) {
    DecodedPacket d;
    if(b.size()<24 || b[0]!=0x55 || b[1]!=0xaa || b[2]!=5 || b[3]!=10) return d;
    d.type=le32(b.data()+4); d.declared_length=le32(b.data()+8);
    size_t fixed=expected_size(d.type);
    if(d.declared_length!=b.size() || (fixed && fixed!=b.size()) ||
       b[b.size()-2]!=0 || b.back()!=0xff ||
       crc32(b.data()+12,b.size()-24)!=le32(b.data()+b.size()-12)) return d;
    d.known=fixed!=0 || d.type==2000 || d.type==2001;
    if(d.type!=102 && d.type!=104) {d.valid=true;return d;}
    const auto* p=b.data()+12;
    d.sequence=le32(p); d.raw_sec=le32(p+8); d.raw_nsec=le32(p+12);
    if(d.type==102) {
        d.sys_rotation_period=le32(p+16);
        d.com_rotation_period=le32(p+20);
        uint32_t up_bits=le32(p+28),down_bits=le32(p+32);
        float up,down; std::memcpy(&up,&up_bits,4); std::memcpy(&down,&down_bits,4);
        if(std::isfinite(up)) d.packet_lost_up=up;
        if(std::isfinite(down)) d.packet_lost_down=down;
    }
    // payload_size is retained on wire but is not used to index storage: its
    // semantics across firmware are not established. Outer fixed size is checked.
    if(*d.raw_nsec>=1000000000u) return d;
    d.raw_timestamp=*d.raw_sec+*d.raw_nsec/1e9;
    if(d.type==104) {
        ImuFrame imu;
        for(size_t i=0;i<10;++i) {
            double v=f32(p+16+4*i); imu.nonfinite+=!std::isfinite(v);
            if(i<4) imu.quaternion[i]=v;
            else if(i<7) imu.angular_velocity[i-4]=v;
            else imu.linear_acceleration[i-7]=v;
        }
        d.imu=imu;
    } else {
        uint32_t n=le32(p+116); if(n>300) return d;
        CloudFrame cloud; cloud.declared_points=n; cloud.points.reserve(n);
        double a=f32(p+52), baxis=f32(p+56), theta_bias=f32(p+60),alpha_bias=f32(p+64);
        double beta=f32(p+68),xi=f32(p+72),bias=f32(p+76),scale=f32(p+80);
        double theta0=f32(p+84),theta_step=f32(p+88),rmin=f32(p+96),rmax=f32(p+100);
        double alpha0=f32(p+104),alpha_step=f32(p+108),dt=f32(p+112);
        double sb=std::sin(beta),cb=std::cos(beta),sx=std::sin(xi),cx=std::cos(xi);
        for(uint32_t i=0;i<n;++i) {
            uint16_t r=uint16_t(p[120+2*i]) | uint16_t(p[121+2*i])<<8;
            if(!r) continue;
            double distance=scale*(r+bias);
            if(distance<rmin || distance>rmax) continue;
            double alpha=alpha0+alpha_bias+i*alpha_step;
            double theta=theta0+theta_bias+i*theta_step;
            double A=(-cb*sx+sb*cx*std::sin(alpha))*distance+baxis;
            double B=std::cos(alpha)*cx*distance;
            double C=(sb*sx+cb*cx*std::sin(alpha))*distance;
            cloud.points.push_back({std::cos(theta)*A-std::sin(theta)*B,
                std::sin(theta)*A+std::cos(theta)*B,C+a,double(p[720+i]),i*dt,1});
        }
        d.cloud=std::move(cloud);
    }
    d.valid=true; return d;
}
}
