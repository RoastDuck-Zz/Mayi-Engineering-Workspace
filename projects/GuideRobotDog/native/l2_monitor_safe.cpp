#include "unitree_lidar_sdk.h"
#include <algorithm>
#include <chrono>
#include <csignal>
#include <cstdlib>
#include <cerrno>
#include <fstream>
#include <sys/wait.h>
#include <sys/resource.h>
#include <unistd.h>
using namespace unilidar_sdk2;
static volatile sig_atomic_t stop_signal=0;
static volatile sig_atomic_t sdk_child=0;
static void on_signal(int s){ stop_signal=s; if(sdk_child>0)kill(sdk_child,s); }
static double mono(){return std::chrono::duration<double>(std::chrono::steady_clock::now().time_since_epoch()).count();}
static void signals(){struct sigaction sa{};sa.sa_handler=on_signal;sigemptyset(&sa.sa_mask);sigaction(SIGINT,&sa,nullptr);sigaction(SIGTERM,&sa,nullptr);}

static int receive(const char* lidar,const char* host,double seconds,const std::string& prefix){
  signals();
  std::ofstream csv(prefix+"-frames.csv"),summary(prefix+"-summary.json");
  if(!csv||!summary)return 20;
  csv<<std::setprecision(16)<<"id,monotonic,host_realtime,device_stamp,points\n";
  summary<<std::setprecision(16);
  auto* reader=createUnitreeLidarReader();
  if(reader->initializeUDP(6101,lidar,6201,host,18,false,0,100))return 21;
  // No mode/config/clock query or mutation commands. SDK initialization is isolated.
  const double start=mono();double last=start,first=0,maxgap=0,next_log=start+10;
  size_t count=0,imus=0,empty=0,invalid=0,imu_invalid=0,parse_errors=0,total_points=0,min_points=SIZE_MAX,max_points=0;
  double ranges_min[4]={1e100,1e100,1e100,1e100},ranges_max[4]={-1e100,-1e100,-1e100,-1e100};
  PointCloudUnitree cloud;LidarImuData imu;
  while(!stop_signal&&mono()-start<seconds){
    int type=reader->runParse();double now=mono();
    if(type==LIDAR_POINT_DATA_PACKET_TYPE&&reader->getPointCloud(cloud)){
      if(!count){first=now;}
      maxgap=std::max(maxgap,now-last);last=now;++count;
      if(cloud.points.empty())++empty;
      total_points+=cloud.points.size();min_points=std::min(min_points,cloud.points.size());max_points=std::max(max_points,cloud.points.size());
      for(const auto& p:cloud.points){
        double v[4]={p.x,p.y,p.z,p.intensity};
        bool finite=std::isfinite(p.time);
        for(int i=0;i<4;++i){finite=finite&&std::isfinite(v[i]);if(std::isfinite(v[i])){ranges_min[i]=std::min(ranges_min[i],v[i]);ranges_max[i]=std::max(ranges_max[i],v[i]);}}
        if(!finite)++invalid;
      }
      csv<<cloud.id<<','<<now<<','<<getSystemTimeStamp()<<','<<cloud.stamp<<','<<cloud.points.size()<<'\n';
    }else if(type==LIDAR_IMU_DATA_PACKET_TYPE&&reader->getImuData(imu)){
      ++imus;
      for(float v:imu.quaternion)if(!std::isfinite(v))++imu_invalid;
      for(float v:imu.angular_velocity)if(!std::isfinite(v))++imu_invalid;
      for(float v:imu.linear_acceleration)if(!std::isfinite(v))++imu_invalid;
    }else if(type<0)++parse_errors;
    else if(type==0)usleep(100);
    if(now>=next_log){std::cout<<"elapsed="<<now-start<<" clouds="<<count<<" imu="<<imus<<'\n'<<std::flush;next_log=now+10;}
  }
  double elapsed=mono()-start;maxgap=std::max(maxgap,mono()-last);
  bool valid=count>0&&empty==0&&invalid==0&&parse_errors==0&&maxgap<1;
  const char* runtime=!valid?"FAIL":elapsed>=60?"PASS":"INCOMPLETE";
  summary<<"{\"runtime_path\":\""<<runtime<<"\",\"cleanup_strategy\":\"isolated process; no closeUDP or SDK destructor\",\"elapsed\":"<<elapsed
    <<",\"clouds\":"<<count<<",\"imu\":"<<imus<<",\"imu_invalid\":"<<imu_invalid<<",\"empty_clouds\":"<<empty<<",\"invalid_points\":"<<invalid
    <<",\"parse_errors\":"<<parse_errors<<",\"max_receive_gap\":"<<maxgap<<",\"average_hz\":"<<(count>1?(count-1)/(last-first):0)
    <<",\"min_points\":"<<(count?min_points:0)<<",\"max_points\":"<<max_points<<",\"average_points\":"<<(count?double(total_points)/count:0)
    <<",\"stopped_by_signal\":"<<stop_signal<<",\"ranges\":[";
  for(int i=0;i<4;++i){if(i)summary<<',';summary<<'['<<ranges_min[i]<<','<<ranges_max[i]<<']';}summary<<"]}\n";
  summary.flush();csv.flush();bool writes_ok=bool(summary)&&bool(csv);summary.close();csv.close();writes_ok=writes_ok&&bool(summary)&&bool(csv);
  std::cout.flush();std::cerr.flush();
  // This function returns only our status; caller uses _Exit, bypassing vendor teardown.
  if(!writes_ok)return 20;
  if(!valid)return 22;
  return elapsed>=60?0:10;
}

int main(int argc,char**argv){
  if(argc!=5){std::cerr<<"Usage: l2_monitor_safe LIDAR_IP HOST_IP SECONDS OUTPUT_PREFIX\n";return 2;}
  double seconds;try{seconds=std::stod(argv[3]);}catch(...){return 2;}
  if(!std::isfinite(seconds)||seconds<1||seconds>600)return 2;
  std::string prefix=argv[4];signals();
  pid_t child=fork();if(child<0)return 23;
  if(child==0){sdk_child=0;int rc=receive(argv[1],argv[2],seconds,prefix);std::_Exit(rc);}
  sdk_child=child;if(stop_signal)kill(child,stop_signal);
  int status=0;double start=mono(),termination=0;bool forced=false;struct rusage usage{};
  for(;;){
    pid_t r=wait4(child,&status,WNOHANG,&usage);if(r==child)break;
    if(r<0&&errno!=EINTR)return 24;
    if(!termination&&(stop_signal||mono()-start>seconds+10)){termination=mono();if(!stop_signal)kill(child,SIGTERM);}
    if(termination&&mono()-termination>5&&!forced){kill(child,SIGKILL);forced=true;}
    usleep(20000);
  }
  sdk_child=0;
  int rc=WIFEXITED(status)?WEXITSTATUS(status):128+WTERMSIG(status);
  const char* cleanup=!forced&&(rc==0||rc==10||rc==22)?"PASS":"FAIL";
  std::ofstream parent(prefix+"-supervisor.json");
  parent<<"{\"child_pid\":"<<child<<",\"child_exit\":"<<rc<<",\"wrapper_cleanup\":\""<<cleanup
    <<"\",\"sdk_cleanup\":\"KNOWN_BUG_AVOIDED\",\"forced_kill\":"<<(forced?"true":"false")
    <<",\"runtime_path\":\""<<(rc==0?"PASS":rc==10?"INCOMPLETE":"FAIL")<<"\",\"max_rss_kib\":"<<usage.ru_maxrss<<"}\n";
  parent.flush();if(!parent)return 20;
  std::cout<<"child_exit="<<rc<<" wrapper_cleanup="<<cleanup<<" SDK_cleanup=KNOWN_BUG_AVOIDED\n";
  return rc;
}
