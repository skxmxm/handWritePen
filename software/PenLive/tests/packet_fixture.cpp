#include <cstdio>
#include "../../../firmware/Pen_R26_Live/BlePacket.h"
int main(){
 PenPacket p={};p.boot=123;p.stroke=4;p.seq=5;p.t_us=1000000;p.opt_us=990000;p.imu_us=980000;p.gsr_us=970000;
 p.x=-2048;p.y=2047;p.angles[0]=-18000;p.angles[1]=9000;p.angles[2]=1234;
 p.accel[0]=1000;p.gyro[2]=-20000;p.battery_mv=3912;p.gsr_raw=1234;p.vex_raw=4000;
 p.flags=ACTIVE|OPT_VALID|IMU_VALID|ACC_VALID|GYRO_VALID|BAT_VALID|ADS_VALID|EXC_ON|GSR_VALID;
 p.imu_baud=9600;p.gsr_state=3;p.stat1=p.stat2=1;
 const auto *bytes=reinterpret_cast<const uint8_t*>(&p);uint16_t crc=penCrc(bytes,sizeof(p));
 for(unsigned i=0;i<sizeof(p);++i)printf("%02x",bytes[i]);printf("%02x%02x\n",crc&255,crc>>8);
}
