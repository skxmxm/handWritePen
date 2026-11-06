#pragma once
#include <stdint.h>
#include "BlePacket.h"

// Passive observation only. Never controls or prolongs GSR excitation.
class BatteryWindow {
 public:
  uint32_t stroke=0;
  uint16_t beforeMv=0,minMv=0,beforeAge=65535;
  uint8_t samples=0;
  bool started=false,running=false,complete=false,beforeValid=false;
  void setOn(bool enabled,uint32_t trial,uint32_t now,bool available,uint16_t mv,uint32_t sampleMs){
    if(!enabled){if(running){running=false;complete=true;}return;}
    if(running)return;
    stroke=trial;started=running=true;complete=false;samples=0;minMv=0;
    startMs=now;lastSampleMs=sampleMs;
    uint32_t age=now-sampleMs;
    beforeValid=available&&age<=100;
    beforeMv=beforeValid?mv:0;beforeAge=beforeValid?uint16_t(age):65535;
  }
  void sample(uint32_t now,uint16_t mv,uint32_t sampleMs){
    if(!running||sampleMs==lastSampleMs||uint32_t(now-sampleMs)>100)return;
    if(uint32_t(sampleMs-startMs)>uint32_t(now-startMs))return; // pre-window data
    lastSampleMs=sampleMs;
    if(!samples||mv<minMv)minMv=mv;
    if(samples<255)++samples;
  }
  uint8_t flags()const{
    return (beforeValid?1:0)|(samples?2:0)|(complete?4:0)|(running?8:0)|(started?16:0);
  }
 private:
  uint32_t startMs=0,lastSampleMs=0;
};

constexpr const char *PEN_POWER_DIAGNOSTIC="7c7b9005-8e77-4b62-9c3d-4d5d83f4a001";
struct __attribute__((packed)) BatteryDiagnostic {
  uint8_t magic,version;
  uint32_t boot,stroke;
  uint8_t flags,samples;
  uint16_t beforeMv,minMv,beforeAge,crc;
};
static_assert(sizeof(BatteryDiagnostic)==20,"Battery diagnostic must fit MTU 23");
inline BatteryDiagnostic makeBatteryDiagnostic(uint32_t boot,const BatteryWindow &w){
  BatteryDiagnostic p={};p.magic=0xD8;p.version=1;p.boot=boot;p.stroke=w.stroke;
  p.flags=w.flags();p.samples=w.samples;p.beforeMv=w.beforeMv;p.minMv=w.minMv;p.beforeAge=w.beforeAge;
  p.crc=penCrc(reinterpret_cast<const uint8_t*>(&p),18);return p;
}
