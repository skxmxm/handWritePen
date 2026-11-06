#include <cassert>
#include <cstdio>
#include <initializer_list>
#include "../../../firmware/Pen_R26_Live/StartupLights.h"

int main(){
 StartupLights lights;
 // Never announce readiness when initialization remains incomplete.
 for(uint32_t now:{0u,500u,5000u,60000u}){
  lights.tick(now,false);
  auto p=lights.levels(now,false,false);
  assert(p.sys&&p.fault&&!lights.running());
 }
 // Sensor/tip states cannot steal either LED during startup.
 lights.tick(60001,true);
 assert(lights.phase()==StartupLights::READY_BLINK);
 unsigned rising=0;bool previous=false;
 for(uint32_t elapsed=0;elapsed<5000;++elapsed){
  lights.tick(60001+elapsed,true);
  auto p=lights.levels(60001+elapsed,elapsed%2,elapsed%3);
  assert(!lights.running()&&p.sys==p.fault);
  assert(p.sys==bool((elapsed/250)%2));
  if(p.sys&&!previous)++rising;
  previous=p.sys;
 }
 assert(rising==10);
 lights.tick(65001,true);assert(lights.running());
 for(bool tip:{false,true})for(bool fault:{false,true}){
  auto p=lights.levels(65001,tip,fault);assert(p.sys==tip&&p.fault==fault);
 }
 lights.tick(65002,false);assert(lights.running()); // Later health changes aren't a reboot.
 StartupLights rollover;
 uint32_t start=0xfffffff0u;rollover.tick(start,true);
 rollover.tick(start+4999u,true);assert(!rollover.running());
 rollover.tick(start+5000u,true);assert(rollover.running());
 puts("PASS: steady startup, service readiness gate, synchronous 10 cycles / 5 seconds, normal handoff, delayed initialization and timer rollover.");
}
