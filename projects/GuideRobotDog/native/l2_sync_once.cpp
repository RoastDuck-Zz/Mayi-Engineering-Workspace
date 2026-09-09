#include "unitree_lidar_sdk.h"
#include <cstdlib>
#include <iostream>
#include <unistd.h>
int main(int argc,char**argv){
 if(argc!=2||std::string(argv[1])!="--authorized-single-epoch-sync")return 2;
 auto* reader=unilidar_sdk2::createUnitreeLidarReader();
 if(reader->initializeUDP(6101,"192.168.1.62",6201,"192.168.1.2",18,false))return 3;
 std::cout<<"Sending syncLidarTimeStamp once; no work-mode, reset, save, IP/MAC or firmware calls\n"<<std::flush;
 reader->syncLidarTimeStamp();
 sleep(1);
 std::cout<<"Sync command emitted; verify offset AND rate independently\n"<<std::flush;
 std::_Exit(0);
}
