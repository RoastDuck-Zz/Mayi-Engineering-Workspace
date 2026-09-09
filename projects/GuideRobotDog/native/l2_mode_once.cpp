#include "unitree_lidar_sdk.h"
#include <cstdlib>
#include <iostream>
#include <unistd.h>
int main(int argc,char**argv){
 if(argc!=2||std::string(argv[1])!="--authorized-mode-zero-reset-once")return 2;
 auto* reader=unilidar_sdk2::createUnitreeLidarReader();
 if(reader->initializeUDP(6101,"192.168.1.62",6201,"192.168.1.2",18,false))return 3;
 std::cout<<"Sending setLidarWorkMode(0) once; no IP/MAC/save/factory-reset/firmware calls\n"<<std::flush;
 reader->setLidarWorkMode(0);
 sleep(1);
 std::cout<<"Sending resetLidar() once\n"<<std::flush;
 reader->resetLidar();
 sleep(1);
 std::cout<<"Commands emitted; device acceptance must be verified independently\n"<<std::flush;
 std::_Exit(0);
}
