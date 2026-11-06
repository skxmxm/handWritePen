#pragma once
#include <Arduino.h>
#include <Wire.h>
#include <esp_timer.h>

// Nonblocking ADS1115 A0/A1 single-shot pair, +/-4.096V, 128SPS.
class AdsPair {
 public:
  explicit AdsPair(TwoWire &wire): bus(wire) {}
  bool valid=false, updated=false;
  int16_t gsr=0,vex=0;
  uint8_t error=0;
  uint32_t pairMs=0;
  uint64_t pairUs=0;
  void reset() {phase=0;next=millis();valid=false;error=0;updated=false;}
  void tick() {
    updated=false;uint32_t now=millis();
    if (phase==0) {
      if (int32_t(now-next)<0)return;
      channel=0;start();return;
    }
    if (uint32_t(now-started)<9)return;
    uint16_t status;
    if (!read(1,status)){fail(1);return;}
    if ((status&0x7fff)!=(config&0x7fff)){fail(2);return;}
    if (!(status&0x8000)){if(uint32_t(now-started)>40)fail(3);return;}
    uint16_t raw;
    if(!read(0,raw)){fail(1);return;}
    int16_t value=(raw&0x8000)?int16_t(int32_t(raw)-65536):int16_t(raw);
    if(channel==0){first=value;channel=1;start();}
    else {gsr=first;vex=value;valid=true;updated=true;error=0;pairMs=millis();
      pairUs=uint64_t(esp_timer_get_time());phase=0;next=pairMs+75;}
  }
 private:
  TwoWire &bus;uint8_t phase=0,channel=0;int16_t first=0;
  uint16_t config=0;uint32_t started=0,next=0;
  void fail(uint8_t e){error=e;valid=false;phase=0;next=millis()+500;}
  bool read(uint8_t reg,uint16_t &value){
    bus.beginTransmission(0x48);bus.write(reg);
    if(bus.endTransmission(false)!=0)return false;
    if(bus.requestFrom(uint8_t(0x48),size_t(2),true)!=2){while(bus.available())bus.read();return false;}
    value=(uint16_t(bus.read())<<8)|uint16_t(bus.read());return true;
  }
  void start(){
    config=0x8000|(uint16_t(4+channel)<<12)|0x0200|0x0100|0x0080|3;
    bus.beginTransmission(0x48);bus.write(1);bus.write(uint8_t(config>>8));bus.write(uint8_t(config));
    if(bus.endTransmission()!=0){fail(1);return;}
    started=millis();phase=1;
  }
};
