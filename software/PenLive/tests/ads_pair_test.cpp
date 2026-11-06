#include <cassert>
#include <cstdio>
#include <initializer_list>
#include "../../../firmware/Pen_R26_Live/AdsPair.h"
uint32_t clockMs=0;
void tick(AdsPair &a,unsigned t){clockMs=t;a.tick();}
int main(){
 TwoWire w;AdsPair a(w);a.reset();tick(a,0);
 assert(w.config==0xc383); // A0, +/-4.096V, single-shot 128SPS, comparator disabled
 tick(a,8);assert(!a.valid);tick(a,9);assert(w.config==0xd383&&!a.valid);
 tick(a,18);assert(a.valid&&a.updated&&a.gsr==1234&&a.vex==4000&&a.pairUs==18000);
 tick(a,19);assert(!a.updated); // old pairs must not count as new measurements
 w.raw[0]=0xffff;w.raw[1]=0x8000;tick(a,93);tick(a,102);tick(a,111);
 assert(a.gsr==-1&&a.vex==-32768); // signed decoding
 // No partial A0 result can publish if A1 fails.
 a.reset();tick(a,120);tick(a,129);w.nack=true;tick(a,138);
 assert(!a.valid&&a.error==1&&!a.updated);w.nack=false;
 tick(a,637);assert(a.error==1);tick(a,638);tick(a,647);tick(a,656);assert(a.valid&&a.error==0);
 a.reset();tick(a,700);w.wrongConfig=true;tick(a,709);assert(a.error==2&&!a.valid);w.wrongConfig=false;
 a.reset();tick(a,800);w.busy=true;tick(a,810);assert(a.error==0);tick(a,841);assert(a.error==3&&!a.valid);w.busy=false;
 a.reset();tick(a,900);w.shortRead=true;tick(a,909);assert(a.error==1&&!a.valid);
 puts("PASS: ADS1115 config/scales, complete pairs, signed data, I2C/config/timeout faults and retry.");
}
