#pragma once
#include <stdint.h>
// Software acquisition gate; the physical USB interlock is independent of this.
class GsrGate {
 public:
  enum Reason:uint8_t {NONE=0,ADC_I2C=1,ADC_CONFIG=2,ADC_TIMEOUT=3,
    OFF_NO_SAMPLE=4,OFF_VOLTAGE=5,ON_NO_SAMPLE=6,ON_STALE=7,ON_LOW=8,ON_HIGH=9};
  uint8_t state=0; // OFF, OFF-check, ON-settling, ON-valid, USB-locked, fault
  bool on=false;
  // Latch the original fault BEFORE disabling output. Retain through pen release.
  uint8_t reason=NONE,faultPhase=0,faultAdc=0;
  int16_t faultVex=0;uint16_t faultAge=0;bool faultValid=false;
  void reset(bool usb=false){on=false;state=usb?4:0;}
  void tick(uint32_t now,bool requested,bool usb,bool updated,bool valid,
            uint8_t error,int16_t vex,uint32_t pairMs){
    if(!requested||usb){reset(usb);return;}
    if(state==5){on=false;return;}
    if(state==0||state==4){
      on=false;state=1;changed=now;
      reason=NONE;faultPhase=faultAdc=0;faultVex=0;faultAge=0;faultValid=false;
    }
    if(error){fault(error<=3?error:ADC_I2C,now,valid,error,vex,pairMs);return;}
    if(state==1){
      if(uint32_t(now-changed)>1000){fault(OFF_NO_SAMPLE,now,valid,error,vex,pairMs);return;}
      if(updated&&valid&&uint32_t(now-changed)>=100){
        if(vex < -400 || vex > 400){fault(OFF_VOLTAGE,now,valid,error,vex,pairMs);return;}
        on=true;state=2;changed=now;
      }
    }else if(state==2||state==3){
      if(!valid){fault(ON_NO_SAMPLE,now,valid,error,vex,pairMs);return;}
      if(uint32_t(now-pairMs)>500){fault(ON_STALE,now,valid,error,vex,pairMs);return;}
      if(updated&&(state==3||uint32_t(now-changed)>=300)){
        if(vex<2800){fault(ON_LOW,now,valid,error,vex,pairMs);return;}
        if(vex>5600){fault(ON_HIGH,now,valid,error,vex,pairMs);return;}
        state=3;
      }
    }
  }
 private:
  uint32_t changed=0;
  void fault(uint8_t why,uint32_t now,bool valid,uint8_t adc,int16_t vex,uint32_t pairMs){
    reason=why;faultPhase=state;faultAdc=adc;faultVex=vex;faultValid=valid;
    uint32_t age=now-pairMs;faultAge=age>65535?65535:uint16_t(age);
    on=false;state=5;
  }
};
