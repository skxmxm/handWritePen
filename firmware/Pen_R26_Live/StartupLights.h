#pragma once
#include <stdint.h>

// One owner writes both LEDs. Tasks publish normal-mode intent only.
// Readiness means services have started, not that every sensor is healthy.
class StartupLights {
 public:
  enum Phase:uint8_t {INITIALIZING, READY_BLINK, RUNNING};
  struct Levels {bool sys,fault;};
  static constexpr uint32_t BLINK_MS=5000, HALF_PERIOD_MS=250;
  Phase phase()const{return phase_;}
  bool running()const{return phase_==RUNNING;}
  void tick(uint32_t now,bool servicesStarted){
    if(phase_==INITIALIZING&&servicesStarted){phase_=READY_BLINK;started_=now;}
    if(phase_==READY_BLINK&&uint32_t(now-started_)>=BLINK_MS)phase_=RUNNING;
  }
  Levels levels(uint32_t now,bool tipDown,bool sensorFault)const{
    if(phase_==INITIALIZING)return {true,true};
    if(phase_==RUNNING)return {tipDown,sensorFault};
    // Begin OFF so the transition from solid ON is visible: ten full cycles.
    bool on=(uint32_t(now-started_)/HALF_PERIOD_MS)%2!=0;
    return {on,on};
  }
 private:
  Phase phase_=INITIALIZING;
  uint32_t started_=0;
};
