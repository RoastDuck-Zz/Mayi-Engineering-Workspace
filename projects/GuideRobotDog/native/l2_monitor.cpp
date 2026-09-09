#include "unitree_lidar_sdk.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <limits>
#include <thread>
using namespace unilidar_sdk2;
using Clock = std::chrono::steady_clock;
double monotonic() { return std::chrono::duration<double>(Clock::now().time_since_epoch()).count(); }
struct Stats {
  uint64_t count=0, gaps=0, backward=0, duplicates=0, resets=0;
  uint32_t seq=0;
  double first=0,last=0,first_m=0,last_m=0,max_gap=0,min_gap=1e100,window_m=0,window_stamp=0;
  void add(uint32_t id,double stamp,double m,const char* name) {
    if (!count) { first=stamp; first_m=m; window_m=m; window_stamp=stamp; }
    else {
      double dt=m-last_m; max_gap=std::max(max_gap,dt); if(dt>0)min_gap=std::min(min_gap,dt);
      if(stamp<=last)++backward;
      uint32_t delta=id-seq;
      if(delta==0)++duplicates;
      else if(delta<0x80000000u)gaps+=delta-1;
      else ++resets;
    }
    ++count; seq=id; last=stamp; last_m=m;
    if(m-window_m>=10) {
      std::cout<<"CLOCK "<<name<<" monotonic_delta="<<m-window_m<<" sensor_delta="<<stamp-window_stamp<<" ratio="<<(stamp-window_stamp)/(m-window_m)<<'\n';
      window_m=m; window_stamp=stamp;
    }
  }
  void json(std::ostream& o) const {
    o<<"{\"count\":"<<count<<",\"sequence_gaps\":"<<gaps<<",\"duplicates\":"<<duplicates<<",\"sequence_resets\":"<<resets
     <<",\"backward\":"<<backward<<",\"first_stamp\":"<<first<<",\"last_stamp\":"<<last
     <<",\"average_hz\":"<<(count>1?(count-1)/(last_m-first_m):0)
     <<",\"min_instant_hz\":"<<(max_gap>0?1/max_gap:0)<<",\"max_instant_hz\":"<<(min_gap<1e99?1/min_gap:0)
     <<",\"max_gap\":"<<max_gap<<",\"clock_ratio\":"<<(count>1?(last-first)/(last_m-first_m):0)<<"}";
  }
};
int main(int argc,char** argv) {
  if(argc!=5) { std::cerr<<"Usage: l2_monitor LIDAR_IP HOST_IP SECONDS OUTPUT_PREFIX\n"; return 2; }
  double seconds=std::stod(argv[3]); if(!std::isfinite(seconds)||seconds<1||seconds>600)return 2;
  std::string prefix=argv[4];
  std::ofstream frames(prefix+"-frames.csv"), summary(prefix+"-summary.json");
  if(!frames||!summary)return 2;
  frames<<"id,monotonic,stamp,points,min_x,max_x,min_y,max_y,min_z,max_z,min_intensity,max_intensity\n"<<std::setprecision(15);
  std::cout<<std::setprecision(15); summary<<std::setprecision(15);
  auto* r=createUnitreeLidarReader();
  // Explicitly preserve hardware time. No mode, reset, sync, IP or motor commands.
  if(r->initializeUDP(6101,argv[1],6201,argv[2],18,false,0,100))return 3;
  std::string version; r->getVersionOfSDK(version); std::cout<<"SDK="<<version<<" hardware_timestamps=true\n";
  // Read-only requests; neither writes configuration nor restarts the sensor.
  r->sendUserCtrlCmd(LidarUserCtrlCmd{USER_CMD_VERSION_GET,0});
  r->sendUserCtrlCmd(LidarUserCtrlCmd{USER_CMD_CONFIG_GET,0});
  Stats cloud_stats, imu_stats, raw_stats;
  PointCloudUnitree cloud; LidarImuData imu;
  uint64_t invalid_points=0,empty_clouds=0,invalid_imu=0,zero_points=0,negative_parse=0,other_packets=0;
  double lo[4]={1e100,1e100,1e100,1e100},hi[4]={-1e100,-1e100,-1e100,-1e100};
  const double start=monotonic(); double report=start;
  while(monotonic()-start<seconds) {
    int type=r->runParse(); double now=monotonic();
    if(type==LIDAR_POINT_DATA_PACKET_TYPE) {
      const auto& p=r->getLidarPointDataPacket();
      raw_stats.add(p.data.info.seq,p.data.info.stamp.sec+p.data.info.stamp.nsec*1e-9,now,"raw_lidar");
      if(r->getPointCloud(cloud)) {
        cloud_stats.add(cloud.id,cloud.stamp,now,"cloud");
        double fmin[4]={1e100,1e100,1e100,1e100},fmax[4]={-1e100,-1e100,-1e100,-1e100};
        if(cloud.points.empty())++empty_clouds;
        for(const auto& p:cloud.points) {
          if(!std::isfinite(p.x)||!std::isfinite(p.y)||!std::isfinite(p.z)||!std::isfinite(p.intensity)||!std::isfinite(p.time)){++invalid_points;continue;}
          if(p.x==0&&p.y==0&&p.z==0)++zero_points;
          double v[4]={p.x,p.y,p.z,p.intensity};
          for(int i=0;i<4;++i){fmin[i]=std::min(fmin[i],v[i]);fmax[i]=std::max(fmax[i],v[i]);lo[i]=std::min(lo[i],v[i]);hi[i]=std::max(hi[i],v[i]);}
        }
        frames<<cloud.id<<','<<now<<','<<cloud.stamp<<','<<cloud.points.size();
        for(int i=0;i<4;++i) { frames<<','<<fmin[i]<<','<<fmax[i]; }
        frames<<'\n';
        // One explicitly bounded real snapshot for client inspection, not continuous recording.
        if(cloud_stats.count==20) {
          std::ofstream pcd(prefix+"-snapshot.xyz");
          for(const auto& p:cloud.points)pcd<<p.x<<' '<<p.y<<' '<<p.z<<' '<<p.intensity<<'\n';
        }
      }
    } else if(type==LIDAR_IMU_DATA_PACKET_TYPE && r->getImuData(imu)) {
      imu_stats.add(imu.info.seq,imu.info.stamp.sec+imu.info.stamp.nsec*1e-9,now,"imu");
      for(float v:imu.quaternion)if(!std::isfinite(v))++invalid_imu;
      for(float v:imu.angular_velocity)if(!std::isfinite(v))++invalid_imu;
      for(float v:imu.linear_acceleration)if(!std::isfinite(v))++invalid_imu;
      if(imu_stats.count==1) { std::cout<<"IMU first quaternion="; for(float v:imu.quaternion)std::cout<<v<<' '; std::cout<<" gyro=";for(float v:imu.angular_velocity)std::cout<<v<<' ';std::cout<<" accel=";for(float v:imu.linear_acceleration)std::cout<<v<<' ';std::cout<<'\n'; }
    } else if(type==0)std::this_thread::sleep_for(std::chrono::microseconds(100));
    else if(type<0)++negative_parse;
    else ++other_packets;
    if(now-report>=1) {
      std::cout<<"t="<<now-start<<" frames="<<cloud_stats.count<<" raw="<<raw_stats.count<<" imu="<<imu_stats.count<<" cached_bytes="<<r->getBufferCachedSize()<<'\n'<<std::flush;
      report=now;
    }
  }
  std::string hw,fw;r->getVersionOfLidarHardware(hw);r->getVersionOfLidarFirmware(fw);
  std::cout<<"hardware="<<hw<<" firmware="<<fw<<'\n';
  summary<<"{\"duration\":"<<monotonic()-start<<",\"cloud\":";cloud_stats.json(summary);
  summary<<",\"imu\":";imu_stats.json(summary);summary<<",\"raw_lidar\":";raw_stats.json(summary);
  summary<<",\"invalid_points\":"<<invalid_points<<",\"empty_clouds\":"<<empty_clouds<<",\"invalid_imu\":"<<invalid_imu
         <<",\"zero_xyz_points\":"<<zero_points<<",\"negative_parse_returns\":"<<negative_parse
         <<",\"packet_errors\":null,\"other_packet_types_count\":"<<other_packets<<",\"ranges\":[";
  for(int i=0;i<4;++i){if(i)summary<<',';summary<<'['<<lo[i]<<','<<hi[i]<<']';}summary<<"]}\n";
  summary.flush(); frames.flush(); std::cout.flush();
  // Preserve the report even if the vendor close routine crashes (observed on Pi).
  std::cerr<<"CHECKPOINT before closeUDP\n";
  r->closeUDP();
  std::cerr<<"CHECKPOINT after closeUDP\n";
  return cloud_stats.count&&imu_stats.count?0:4;
}
