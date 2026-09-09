#include "unitree_lidar_sdk.h"
#include <unistd.h>
int main() {
  auto* reader=unilidar_sdk2::createUnitreeLidarReader();
  if(reader->initializeUDP(6101,"192.168.1.62",6201,"192.168.1.2",18,false))return 3;
  sleep(2);
  reader->closeUDP();
  return 0;
}
