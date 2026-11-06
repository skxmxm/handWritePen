#include <cassert>
#include <cstdio>
#include <initializer_list>
#include "../../../firmware/Pen_R26_Live/GsrGate.h"
void tick(GsrGate &g,unsigned now,int vex,bool request=true,bool usb=false,bool update=true,bool valid=true,int error=0,int age=0){
 g.tick(now,request,usb,update,valid,error,vex,now-age);
}
void ready(GsrGate &g){g.reset();tick(g,0,0);tick(g,100,0);tick(g,400,4000);assert(g.state==3&&g.on);}
int main(){
 GsrGate g;tick(g,0,0);assert(g.state==1&&!g.on);
 tick(g,99,0);assert(!g.on);tick(g,100,0);assert(g.state==2&&g.on);
 tick(g,399,0);assert(g.state==2);tick(g,400,4000);assert(g.state==3&&g.on);
 // USB, cancelled request and connection loss inhibit every phase, even without an ADC update.
 for(int phase=0;phase<6;++phase){
  for(bool usb:{false,true}){g.state=phase;g.on=true;tick(g,900,4000,false,usb,false);assert(!g.on);assert(g.state==(usb?4:0));}
  g.state=phase;g.on=true;tick(g,900,4000,true,true,false);assert(!g.on&&g.state==4);
 }
 g.reset();tick(g,0,0);tick(g,100,401);assert(g.state==5&&!g.on);
 tick(g,200,0);assert(g.state==5&&!g.on); // fault cannot restart while request remains active
 tick(g,300,0,false);assert(g.state==0); // cancelled request rearms
 ready(g);tick(g,401,2799);assert(g.state==5&&!g.on);
 ready(g);tick(g,401,5601);assert(g.state==5&&!g.on);
 ready(g);tick(g,1000,4000,true,false,false,true,0,501);assert(g.state==5&&!g.on);
 for(int e=1;e<=3;++e){ready(g);tick(g,401,4000,true,false,false,false,e);assert(!g.on&&g.state==5);}
 g.reset();tick(g,0,0);tick(g,1001,0,true,false,false);assert(!g.on&&g.state==5);
 // millis rollover must not skip the stable OFF and ON waiting intervals.
 g.reset();tick(g,0xffffffcd,0);tick(g,49,0);assert(g.on&&g.state==2);
 tick(g,349,4000);assert(g.on&&g.state==3);
 // Preserve the first fault voltage before turning excitation off, including release.
 g.reset();tick(g,0,0);tick(g,100,0);tick(g,400,8,true,false,true,true,0,2);
 assert(g.reason==GsrGate::ON_LOW&&g.faultPhase==2&&g.faultVex==8&&g.faultAge==2&&g.faultValid);
 tick(g,500,0);tick(g,600,0,false);assert(g.faultVex==8&&g.reason==GsrGate::ON_LOW);
 tick(g,700,0);assert(g.reason==0&&g.state==1); // Only a new trial clears the firmware latch.
 tick(g,800,-401);assert(g.reason==GsrGate::OFF_VOLTAGE&&g.faultPhase==1&&g.faultVex==-401);
 ready(g);tick(g,401,5601);assert(g.reason==GsrGate::ON_HIGH&&g.faultPhase==3);
 ready(g);tick(g,1000,4000,true,false,false,true,0,501);assert(g.reason==GsrGate::ON_STALE&&g.faultAge==501);
 ready(g);tick(g,401,4000,true,false,false,false);assert(g.reason==GsrGate::ON_NO_SAMPLE&&!g.faultValid);
 for(int e=1;e<=3;++e){ready(g);tick(g,401,4000,true,false,false,false,e);assert(g.reason==e&&g.faultAdc==e&&!g.faultValid);}
 g.reset();tick(g,0,0);tick(g,1001,0,true,false,false);assert(g.reason==GsrGate::OFF_NO_SAMPLE&&g.faultPhase==1);
 // Exact voltage boundaries and timing remain unchanged.
 for(int off:{-400,400})for(int on:{2800,5600}){
  g.reset();tick(g,0,0);tick(g,100,off);tick(g,400,on);assert(g.on&&g.state==3&&g.reason==0);
 }
 // Continuous request remains enabled across long acquisition; no tip event
 // is involved in this gate. A cancelled BLE request always disables output.
 ready(g);
 for(unsigned now=500;now<120000;now+=100){tick(g,now,4184);assert(g.on&&g.state==3);}
 tick(g,120000,4184,false);assert(!g.on&&g.state==0);
 puts("PASS: GSR gates, USB/release/link inhibition, exact boundaries, ADC faults, stale data, rollover, and retained fault reason/phase/voltage.");
}
