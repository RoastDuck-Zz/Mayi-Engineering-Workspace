#include "unitree_lidar_sdk.h"
#include "unitree_lidar_protocol.h"
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <optional>
#include <thread>
#include <algorithm>
#include <vector>
using namespace unilidar_sdk2;
using Clock=std::chrono::steady_clock;
static double mono(){return std::chrono::duration<double>(Clock::now().time_since_epoch()).count();}
struct Stream {uint64_t count=0,gaps=0,duplicates=0;uint32_t first=0,last=0;double raw_first=0,raw_last=0,host_first=0,host_last=0;std::vector<double> raw_periods;std::vector<float> up,down;uint64_t up_changed=0,down_changed=0;void add(uint32_t s,double r,double h,std::optional<float> u={},std::optional<float>d={}){if(count){uint32_t x=s-last;if(x==0)++duplicates;else if(x<0x80000000u)gaps+=x-1; if(x==1&&r>=raw_last)raw_periods.push_back(r-raw_last);}else{first=s;raw_first=r;host_first=h;}if(u){if(!up.empty()&&up.back()!=*u)++up_changed;up.push_back(*u);}if(d){if(!down.empty()&&down.back()!=*d)++down_changed;down.push_back(*d);}last=s;raw_last=r;host_last=h;++count;}};
static double median(std::vector<double> v){if(v.empty())return 0;std::sort(v.begin(),v.end());return v[v.size()/2];}
static void json_stream(std::ostream&o,const Stream&s,double host_elapsed){double nom=median(s.raw_periods),positions=double(s.count+s.gaps);double raw_rate=(host_elapsed>0&&nom>0&&positions>1)?(positions-1)*nom/host_elapsed:0;o<<"{\"raw_packets\":"<<s.count<<",\"first_seq\":"<<s.first<<",\"last_seq\":"<<s.last<<",\"gap_events\":\"unknown\",\"estimated_missing\":"<<s.gaps<<",\"duplicates\":"<<s.duplicates<<",\"missing_fraction\":"<<(s.count+s.gaps?double(s.gaps)/(s.count+s.gaps):0)<<",\"raw_ratio\":"<<raw_rate<<",\"nominal_raw_period\":"<<nom<<",\"packet_lost_up_changed\":"<<s.up_changed<<",\"packet_lost_down_changed\":"<<s.down_changed<<"}";}
int main(int argc,char**argv){if(argc!=2){std::cerr<<"usage: l2_official_sdk_probe SECONDS\n";return 2;}int sec=std::stoi(argv[1]);if(sec<1||sec>60)return 2;auto*r=createUnitreeLidarReader();if(r->initializeUDP(6101,"192.168.1.62",6201,"192.168.1.2",1,false,0,100)!=0){std::cerr<<"initializeUDP failed\n";return 3;}Stream cloud,imu;double start=mono();int negative=0;while(mono()-start<sec){int t=r->runParse();double h=mono();if(t==LIDAR_POINT_DATA_PACKET_TYPE){const auto&p=r->getLidarPointDataPacket();double raw=p.data.info.stamp.sec+p.data.info.stamp.nsec/1e9;cloud.add(p.data.info.seq,raw,h,p.data.state.packet_lost_up,p.data.state.packet_lost_down);}else if(t==LIDAR_IMU_DATA_PACKET_TYPE){const auto&p=r->getLidarImuDataPacket();double raw=p.data.info.stamp.sec+p.data.info.stamp.nsec/1e9;imu.add(p.data.info.seq,raw,h);}else if(t<0)++negative;else if(t==0)std::this_thread::sleep_for(std::chrono::microseconds(100));}double elapsed=mono()-start;std::cout<<std::setprecision(17)<<"{\"duration\":"<<elapsed<<",\"runParse_negative\":"<<negative<<",\"cloud\":";json_stream(std::cout,cloud,elapsed);std::cout<<",\"imu\":";json_stream(std::cout,imu,elapsed);std::cout<<",\"cleanup\":\"pending\"}\n"<<std::flush;std::cerr<<"CHECKPOINT before closeUDP\n";r->closeUDP();std::cerr<<"CHECKPOINT after closeUDP\n";return cloud.count&&imu.count?0:4;}
