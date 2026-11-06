#include <cstdio>
#include "../../../firmware/Pen_R26_Live/BlePacket.h"
int main(){
 PenPacket p={};p.boot=987;p.seq=1;p.t_us=p.gsr_us=100000;
 p.battery_mv=3900;p.gsr_raw=-1;p.flags=RAW_OFF_MODE|ADS_VALID|BAT_VALID;
 p.gsr_state=6;p.stat1=p.stat2=1;
 const auto *bytes=reinterpret_cast<const uint8_t*>(&p);
 uint16_t crc=penCrc(bytes,sizeof(p));
 for(unsigned i=0;i<sizeof(p);++i)printf("%02x",bytes[i]);
 printf("%02x%02x\n",crc&255,crc>>8);
}
