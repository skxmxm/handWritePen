#include <cassert>
#include <cstdio>
#include "../../../firmware/Pen_R26_Live/BatteryWindow.h"
int main(){
 BatteryWindow w;assert(w.flags()==0);
 w.setOn(true,7,1000,true,4020,970);
 assert(w.beforeValid&&w.beforeMv==4020&&w.beforeAge==30&&w.running);
 w.sample(1000,4020,970);assert(w.samples==0); // baseline is not an ON sample
 w.sample(1010,4000,990);assert(w.samples==0); // acquisition preceded switch-on
 w.sample(1050,3980,1050);w.sample(1051,3900,1050);assert(w.samples==1&&w.minMv==3980);
 w.sample(1100,3740,1100);w.sample(1150,3980,1150);assert(w.samples==3&&w.minMv==3740);
 w.setOn(false,7,1200,false,0,0);w.sample(1250,3200,1250);
 assert(w.complete&&!w.running&&w.samples==3&&w.minMv==3740);
 w.setOn(false,8,1300,true,4200,1300);assert(w.stroke==7&&w.beforeMv==4020);
 w.setOn(true,8,2000,true,4200,1800);assert(!w.beforeValid&&w.beforeAge==65535&&w.samples==0);
 w.sample(2200,2000,2001);assert(w.samples==0); // stale
 w.sample(2250,2100,2250);assert(w.samples==1&&w.minMv==2100); // do not hide deep sag
 w.setOn(false,8,2300,false,0,0);
 w.setOn(true,9,0xfffffff0,true,4000,0xffffffe0);
 w.sample(0x22,3800,0x22);assert(w.samples==1&&w.beforeAge==16&&w.minMv==3800);
 for(uint32_t n=0;n<300;++n)w.sample(0x54+n*50,3790,0x54+n*50);
 assert(w.samples==255&&w.minMv==3790);
 w.setOn(false,9,20000,false,0,0);
 w.setOn(true,10,21000,false,0,0);w.setOn(false,10,21001,false,0,0);
 assert(w.complete&&!w.beforeValid&&!w.samples&&w.flags()==20);
 puts("PASS: battery window baseline age, sample freshness, no pre-ON samples, minimum retention, release, deep sag, counter saturation and timer rollover.");
}
