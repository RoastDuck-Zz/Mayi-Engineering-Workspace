#include "unitree_lidar_protocol.h"
#include <cstddef>
#include <iostream>
using namespace unilidar_sdk2;
int main(){
 std::cout<<"FrameHeader="<<sizeof(FrameHeader)<<" FrameTail="<<sizeof(FrameTail)
 <<" DataInfo="<<sizeof(DataInfo)<<" ImuPayload="<<sizeof(LidarImuData)<<" ImuFrame="<<sizeof(LidarImuDataPacket)
 <<" PointFrame="<<sizeof(LidarPointDataPacket)<<" stamp_offset_payload="<<offsetof(DataInfo,stamp)
 <<" quaternion_offset_payload="<<offsetof(LidarImuData,quaternion)<<'\n';
}
