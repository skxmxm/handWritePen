/* R26 v0.61: startup LED sequence + independent buffered acquisition.
 * Optical Wire: core 1 / priority 3, 200 Hz target. AFE+UART: core 1 / priority 2.
 * Arduino loop owns every BLE send; only short snapshot copies hold dataMux.
 * Battery-only GSR is continuous while subscribed, independent of the tip.
 */
#include <Arduino.h>
#include <Wire.h>
#include <driver/gpio.h>
#include <esp_timer.h>
#include <esp_system.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLE2902.h>
#include <atomic>
#include "Pat9125.h"
#include "Jy901Parser.h"
#include "AdsPair.h"
#include "BlePacket.h"
#include "OpticalPacket.h"
#include "GsrGate.h"
#include "GsrDiagnostic.h"
#include "BatteryWindow.h"
#include "PenPosition.h"
#include "StartupLights.h"
#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Select ESP32S3 Dev Module."
#endif
constexpr bool ALLOW_USB_CHARGING=true;
constexpr uint32_t IMU_FIXED_BAUD=0;
constexpr float BATTERY_CAL=1.0f;
constexpr uint8_t TIP=11,SYS_LED=12,FAULT_LED=13,USB_ABSENT=14,STAT1=15,STAT2=16;
constexpr uint8_t GSR_EN=7,CHG_EN=21,BAT_EN=48,BAT_ADC=1;
constexpr uint16_t BLE_INTERVAL_UNITS=12; // 15 ms request, peer decides.
constexpr uint32_t BAUDS[]={9600,115200,57600,38400,19200,4800,230400};
constexpr uint32_t OPTICAL_PERIOD_MS=5;
HardwareSerial imuSerial(1);TwoWire afe(1);
Pat9125 optical(Wire,0x75);Jy901Parser imu;AdsPair ads(afe);
GsrGate gsrGate;BatteryWindow batteryWindow;
BLEServer *server=nullptr;
BLECharacteristic *notifyChar=nullptr,*opticalChar=nullptr,*diagnosticChar=nullptr,*powerChar=nullptr;
BLE2902 *cccd=nullptr,*opticalCccd=nullptr,*diagnosticCccd=nullptr,*powerCccd=nullptr;
std::atomic<bool> bleLink(false),subscribed(false),optSubscribed(false),smallMtu(false);
std::atomic<bool> retryOptical(false),retrySensors(false),optFault(true);
std::atomic<bool> opticalStarted(false),sensorsStarted(false),systemReady(false);
std::atomic<bool> tipLed(false),faultLed(true);
StartupLights startupLights;
std::atomic<uint32_t> acquiredCount(0),droppedCount(0);
uint32_t bootId=0;
QueueHandle_t opticalQueue=nullptr;
portMUX_TYPE dataMux=portMUX_INITIALIZER_UNLOCKED;
struct OpticalState {int32_t x=0,y=0;uint32_t stroke=0,errors=0;uint64_t us=0;bool down=false,valid=false;};
OpticalState sharedOpt;
PenPacket sharedSensors={};GsrDiagnostic sharedDiagnostic={};BatteryDiagnostic sharedPower={};
uint64_t us(){return uint64_t(esp_timer_get_time());}
bool usbPresent(){return digitalRead(USB_ABSENT)==LOW;}
bool linked(){return systemReady.load()&&bleLink.load()&&subscribed.load();}
bool fresh(const Jy901Parser::Reading&r,uint64_t now){return r.valid&&now>=r.us&&now-r.us<=250000;}
void excitationOff(){digitalWrite(GSR_EN,LOW);gsrGate.on=false;}
class ServerCB:public BLEServerCallbacks {
 void onConnect(BLEServer*s,esp_ble_gatts_cb_param_t*p)override{
  bleLink=true;s->updateConnParams(p->connect.remote_bda,BLE_INTERVAL_UNITS,BLE_INTERVAL_UNITS,0,400);
 }
 void onDisconnect(BLEServer*)override{
  bleLink=false;subscribed=false;optSubscribed=false;
  // A new client must subscribe explicitly; do not inherit the previous CCCDs.
  for(auto descriptor:{cccd,opticalCccd,diagnosticCccd,powerCccd})
   if(descriptor)descriptor->setNotifications(false);
 }
};
class CommandCB:public BLECharacteristicCallbacks {
 void onWrite(BLECharacteristic*c)override{
  String v=c->getValue();if(v.length()&&v[0]=='i'){retryOptical=true;retrySensors=true;}
 }
};

// Only this task touches Wire, the PAT driver and optical position.
void opticalTask(void*){
 Wire.begin(9,8,100000);Wire.setTimeOut(10); // Keep verified bus electrical timing.
 gpio_pullup_dis(GPIO_NUM_9);gpio_pulldown_dis(GPIO_NUM_9);
 gpio_pullup_dis(GPIO_NUM_8);gpio_pulldown_dis(GPIO_NUM_8);
 bool healthy=optical.begin(),rawDown=digitalRead(TIP)==LOW,stableDown=false;
 uint32_t changed=millis(),stroke=0,sequence=0,errors=0,lastPublished=0;
 uint8_t failures=0;PenPosition position;TickType_t due=xTaskGetTickCount();
 for(;;){
  if(retryOptical.exchange(false)){optical.stop();healthy=optical.begin();failures=0;++errors;}
  uint32_t now=millis();bool raw=digitalRead(TIP)==LOW;
  if(raw!=rawDown){rawDown=raw;changed=now;}
  bool edge=rawDown!=stableDown&&uint32_t(now-changed)>=10;
  if(edge){stableDown=rawDown;if(stableDown)++stroke;}
  tipLed=stableDown; // Startup coordinator owns the physical LEDs.
  bool valid=false;Pat9125::Motion motion={};
  if(optical.ready()){
   ++acquiredCount;
   if(optical.poll(motion)&&position.add(motion.dx,motion.dy)){valid=healthy=true;failures=0;}
   else{healthy=false;++errors;if(++failures>=3)optical.stop();}
  }
  uint64_t stamp=us();optFault=!healthy;
  OpticalState snapshot={position.x,position.y,stroke,errors,stamp,stableDown,valid};
  portENTER_CRITICAL(&dataMux);sharedOpt=snapshot;portEXIT_CRITICAL(&dataMux);
  opticalStarted=true; // First initialization attempt and polling pass finished.
  // Small MTU: keep integrating at 200 Hz but publish absolute positions at 50 Hz.
  // Edges always get a sample; sequence gaps expose queue loss to the host.
  if(bleLink.load()&&optSubscribed.load()&&
     (edge||!smallMtu.load()||uint32_t(now-lastPublished)>=20)){
   OpticalRecord r={++sequence,stamp,position.x,position.y,stroke,
     uint8_t((stableDown?PEN_DOWN:0)|(valid?MOTION_VALID:0)|(edge?TIP_BOUNDARY:0))};
   if(xQueueSend(opticalQueue,&r,0)!=pdTRUE){
    OpticalRecord discarded;if(xQueueReceive(opticalQueue,&discarded,0)==pdTRUE)++droppedCount;
    if(xQueueSend(opticalQueue,&r,0)!=pdTRUE)++droppedCount;
   }
   lastPublished=now;
  }
  if(xTaskGetTickCount()-due>pdMS_TO_TICKS(OPTICAL_PERIOD_MS))due=xTaskGetTickCount();
  vTaskDelayUntil(&due,pdMS_TO_TICKS(OPTICAL_PERIOD_MS));
 }
}

// Only this task owns AFE I2C, UART, the excitation state machine and battery ADC.
void sensorTask(void*){
 imuSerial.setRxBufferSize(2048);uint8_t baudIndex=0;uint32_t baud=IMU_FIXED_BAUD?IMU_FIXED_BAUD:BAUDS[0];
 bool imuLocked=false;uint32_t scanStart=millis();
 auto startImu=[&](){imuSerial.end();imu.reset();imuLocked=false;imuSerial.begin(baud,SERIAL_8N1,18,17);scanStart=millis();};
 startImu();afe.begin(4,5,100000);afe.setTimeOut(10);ads.reset();
 uint32_t gsrSession=0,faultSession=0,batStarted=0,batNext=0,batSampleMs=0,batPublished=0,lastPublish=0;
 uint16_t batSampleMv=0,batteryMv=0;bool measuring=false,batAvailable=false,batteryValid=false;
 for(;;){
  bool requested=linked();bool usb=usbPresent();
  if(!requested||usb)excitationOff(); // Before possibly slow sensor I/O. USB hardware clamp remains.
  digitalWrite(CHG_EN,ALLOW_USB_CHARGING&&usb?HIGH:LOW);
  if(retrySensors.exchange(false)){excitationOff();gsrGate.reset(usb);ads.reset();}
  unsigned budget=512;while(budget--&&imuSerial.available())imu.feed(uint8_t(imuSerial.read()),us());
  if(imu.frames>=3&&imu.angle.valid)imuLocked=true;
  if(!IMU_FIXED_BAUD&&((!imuLocked&&uint32_t(millis()-scanStart)>1300)||(imuLocked&&us()-imu.lastFrameUs>3000000))){
   baudIndex=(baudIndex+1)%(sizeof(BAUDS)/sizeof(BAUDS[0]));baud=BAUDS[baudIndex];startImu();
  }
  uint32_t now=millis();
  if(!measuring&&(requested||int32_t(now-batNext)>=0)){digitalWrite(BAT_EN,HIGH);batStarted=now;measuring=true;batAvailable=false;}
  if(measuring&&uint32_t(now-batStarted)>=150&&(!batAvailable||uint32_t(now-batSampleMs)>=50)){
   uint32_t sum=0;for(int i=0;i<8;++i)sum+=analogReadMilliVolts(BAT_ADC);
   batSampleMv=uint16_t(lroundf(sum/8.0f*2.0f*BATTERY_CAL));batSampleMs=millis();batAvailable=true;
   batteryWindow.sample(batSampleMs,batSampleMv,batSampleMs);
   if(!batteryValid||uint32_t(batSampleMs-batPublished)>=1000){batteryMv=batSampleMv;batteryValid=batteryMv>=2400&&batteryMv<=4400;batPublished=batSampleMs;}
   if(!requested){digitalWrite(BAT_EN,LOW);measuring=false;batNext=millis()+850;}
  }
  ads.tick();now=millis();requested=linked();usb=usbPresent();
  uint8_t previous=gsrGate.state;
  if(requested&&!usb&&(previous==0||previous==4))++gsrSession;
  gsrGate.tick(now,requested,usb,ads.updated,ads.valid,ads.error,ads.vex,ads.pairMs);
  if(gsrGate.state==5&&previous!=5)faultSession=gsrSession;
  if(usbPresent()||!linked())gsrGate.reset(usbPresent());
  digitalWrite(GSR_EN,gsrGate.on?HIGH:LOW);
  batteryWindow.setOn(gsrGate.on,gsrSession,now,batAvailable,batSampleMv,batSampleMs);
  if(uint32_t(now-lastPublish)>=5){
   PenPacket p={};p.t_us=us();p.imu_us=imu.angle.us;p.gsr_us=ads.pairUs;p.battery_mv=batteryMv;p.imu_baud=baud;
   p.gsr_state=gsrGate.state;p.ads_error=ads.error;p.stat1=digitalRead(STAT1);p.stat2=digitalRead(STAT2);
   auto pack=[&](const Jy901Parser::Reading&r,int16_t*out,float scale,uint16_t flag){
    if(fresh(r,p.t_us)){for(int i=0;i<3;++i)out[i]=int16_t(lroundf(r.v[i]*scale));p.flags|=flag;}
   };
   pack(imu.angle,p.angles,100,IMU_VALID);pack(imu.accel,p.accel,1000,ACC_VALID);pack(imu.gyro,p.gyro,10,GYRO_VALID);
   if(batteryValid)p.flags|=BAT_VALID;
   if(ads.valid&&uint32_t(now-ads.pairMs)<500){p.flags|=ADS_VALID;p.gsr_raw=ads.gsr;p.vex_raw=ads.vex;}
   if(gsrGate.on)p.flags|=EXC_ON;
   if(gsrGate.state==3&&!usb&&(p.flags&ADS_VALID))p.flags|=GSR_VALID;
   if(usb)p.flags|=USB_IN;if(ALLOW_USB_CHARGING&&usb)p.flags|=CHARGE_EN;
   GsrDiagnostic diagnostic=makeDiagnostic(bootId,gsrGate.reason?faultSession:gsrSession,gsrGate);
   BatteryDiagnostic power=makeBatteryDiagnostic(bootId,batteryWindow);
   portENTER_CRITICAL(&dataMux);sharedSensors=p;sharedDiagnostic=diagnostic;sharedPower=power;portEXIT_CRITICAL(&dataMux);
   // Do not wait forever for an absent sensor. Errors remain visible in normal mode.
   if(ads.valid||ads.error)sensorsStarted=true;
   lastPublish=now;
  }
  faultLed=optFault.load()||!fresh(imu.angle,us())||gsrGate.state==5||ads.error;
  vTaskDelay(1);
 }
}

struct Pending {
 uint8_t bytes[OPTICAL_BODY_MAX];unsigned length=0,offset=0,chunk=0,index=0,count=0;uint16_t id=0;
 void begin(unsigned n,unsigned mtu){length=n;offset=index=0;++id;chunk=min(176u,max(14u,mtu>9?mtu-9:14));count=(n+chunk-1)/chunk;}
 void send(BLECharacteristic*c,uint8_t magic,uint8_t version){
  uint8_t b[182]={magic,version,uint8_t(id),uint8_t(id>>8),uint8_t(index),uint8_t(count)};
  unsigned n=min(chunk,length-offset);memcpy(b+6,bytes+offset,n);c->setValue(b,n+6);c->notify();
  offset+=n;++index;if(offset==length)length=0;
 }
};
Pending telemetryPending,opticalPending;
uint32_t sequence=0,lastTelemetry=0,lastOptical=0,lastFragment=0,lastDiagnostic=0;
bool oldLink=false,oldOptSubscription=false,sendOptNext=true;
void initOutput(uint8_t pin,uint8_t level){
 // Preload the latch, then register the GPIO before using Arduino digitalWrite.
 // Arduino-ESP32 3.x ignores digitalWrite on an unconfigured pin.
 gpio_set_level(static_cast<gpio_num_t>(pin),level);
 pinMode(pin,OUTPUT);digitalWrite(pin,level);
}
void setStatusLeds(bool sys,bool fault){
 digitalWrite(SYS_LED,sys?HIGH:LOW);digitalWrite(FAULT_LED,fault?HIGH:LOW);
}
void fatalStartup(){
 systemReady=false;subscribed=false;optSubscribed=false;
 digitalWrite(GSR_EN,LOW);setStatusLeds(false,true);
 for(;;)delay(1000);
}
void setup(){
 // Earliest application indication; ROM/bootloader time precedes setup().
 for(uint8_t pin:{SYS_LED,FAULT_LED})initOutput(pin,HIGH);
 for(uint8_t pin:{GSR_EN,CHG_EN,BAT_EN})initOutput(pin,LOW);
 for(uint8_t pin:{TIP,USB_ABSENT,STAT1,STAT2})pinMode(pin,INPUT);
 analogReadResolution(12);analogSetPinAttenuation(BAT_ADC,ADC_11db);bootId=esp_random();
 opticalQueue=xQueueCreate(256,sizeof(OpticalRecord));
 if(!opticalQueue)fatalStartup();
 BLEDevice::init("SmartPen-R26");BLEDevice::setMTU(185);BLEDevice::setPower(ESP_PWR_LVL_N0);
 server=BLEDevice::createServer();server->setCallbacks(new ServerCB());
 BLEService *svc=server->createService(BLEUUID(PEN_SERVICE),24);
 auto addNotify=[&](const char*uuid,BLECharacteristic*&c,BLE2902*&descriptor,bool readable){
  c=svc->createCharacteristic(uuid,BLECharacteristic::PROPERTY_NOTIFY|(readable?BLECharacteristic::PROPERTY_READ:0));
  descriptor=new BLE2902();c->addDescriptor(descriptor);
 };
 addNotify(PEN_NOTIFY,notifyChar,cccd,false);addNotify(PEN_OPTICAL,opticalChar,opticalCccd,false);
 addNotify(PEN_DIAGNOSTIC,diagnosticChar,diagnosticCccd,true);addNotify(PEN_POWER_DIAGNOSTIC,powerChar,powerCccd,true);
 auto control=svc->createCharacteristic(PEN_CONTROL,BLECharacteristic::PROPERTY_WRITE);control->setCallbacks(new CommandCB());
 // Publish a valid empty diagnostic before subscriptions can arrive.
 GsrDiagnostic initial=makeDiagnostic(bootId,0,gsrGate);diagnosticChar->setValue(reinterpret_cast<uint8_t*>(&initial),sizeof(initial));
 BatteryDiagnostic initialPower=makeBatteryDiagnostic(bootId,batteryWindow);powerChar->setValue(reinterpret_cast<uint8_t*>(&initialPower),sizeof(initialPower));
 svc->start();BLEAdvertising *ad=BLEDevice::getAdvertising();ad->addServiceUUID(PEN_SERVICE);ad->setScanResponse(true);
 ad->setMinPreferred(BLE_INTERVAL_UNITS);ad->setMaxPreferred(BLE_INTERVAL_UNITS);
 // Start advertising only after both services start and the 5 s blink completes.
 if(xTaskCreatePinnedToCore(opticalTask,"pen_optical",4096,nullptr,3,nullptr,1)!=pdPASS||
    xTaskCreatePinnedToCore(sensorTask,"pen_sensors",6144,nullptr,2,nullptr,1)!=pdPASS){
  fatalStartup();
 }
}
void loop(){
 uint32_t lightNow=millis();
 startupLights.tick(lightNow,opticalStarted.load()&&sensorsStarted.load());
 auto lights=startupLights.levels(lightNow,tipLed.load(),faultLed.load());
 setStatusLeds(lights.sys,lights.fault);
 if(!startupLights.running()){delay(1);return;}
 if(!systemReady.exchange(true))BLEDevice::startAdvertising();
 bool link=bleLink.load();bool data=link&&cccd->getNotifications();bool optics=link&&opticalCccd->getNotifications();
 subscribed=data;
 if(optics&&!oldOptSubscription)xQueueReset(opticalQueue);
 optSubscribed=optics;oldOptSubscription=optics;
 if(!link&&oldLink)BLEDevice::startAdvertising();oldLink=link;
 if(!data)telemetryPending.length=0;if(!optics){opticalPending.length=0;xQueueReset(opticalQueue);}
 unsigned mtu=link?server->getPeerMTU(server->getConnId()):23;smallMtu=mtu<105;
 uint32_t now=millis();
 if(data&&!telemetryPending.length&&uint32_t(now-lastTelemetry)>=(smallMtu.load()?100:40)){
  PenPacket p;OpticalState o;
  portENTER_CRITICAL(&dataMux);p=sharedSensors;o=sharedOpt;portEXIT_CRITICAL(&dataMux);
  p.boot=bootId;p.seq=++sequence;p.t_us=us();p.opt_us=o.us;p.x=o.x;p.y=o.y;p.stroke=o.stroke;p.opt_errors=o.errors;
  if(o.down)p.flags|=ACTIVE;if(o.valid)p.flags|=OPT_VALID;
  memcpy(telemetryPending.bytes,&p,sizeof(p));uint16_t crc=penCrc(telemetryPending.bytes,sizeof(p));
  telemetryPending.bytes[sizeof(p)]=crc&255;telemetryPending.bytes[sizeof(p)+1]=crc>>8;
  telemetryPending.begin(sizeof(p)+2,mtu);lastTelemetry=now;
 }
 if(optics&&!opticalPending.length&&uint32_t(now-lastOptical)>=20){
  // Bound backlog to roughly 120 ms. Missing sequence numbers break ink on the PC.
  OpticalRecord discarded;while(uxQueueMessagesWaiting(opticalQueue)>24){if(xQueueReceive(opticalQueue,&discarded,0)==pdTRUE)++droppedCount;}
  OpticalRecord records[OPTICAL_BATCH_MAX];unsigned count=0,limit=smallMtu.load()?1:OPTICAL_BATCH_MAX;
  while(count<limit&&xQueueReceive(opticalQueue,&records[count],0)==pdTRUE)++count;
  unsigned n=packOptical(opticalPending.bytes,bootId,acquiredCount.load(),droppedCount.load(),records,count);
  if(n)opticalPending.begin(n,mtu);lastOptical=now;
 }
 if(link&&uint32_t(now-lastFragment)>=1&&(opticalPending.length||telemetryPending.length)){
  if(opticalPending.length&&(sendOptNext||!telemetryPending.length)){opticalPending.send(opticalChar,0xA6,1);sendOptNext=false;}
  else{telemetryPending.send(notifyChar,0xA5,PEN_WIRE_VERSION);sendOptNext=true;}
  lastFragment=millis();
 }
 if(link&&uint32_t(now-lastDiagnostic)>=200){
  GsrDiagnostic d;BatteryDiagnostic b;
  portENTER_CRITICAL(&dataMux);d=sharedDiagnostic;b=sharedPower;portEXIT_CRITICAL(&dataMux);
  if(d.magic==0xD7){diagnosticChar->setValue(reinterpret_cast<uint8_t*>(&d),sizeof(d));if(diagnosticCccd->getNotifications())diagnosticChar->notify();}
  if(b.magic==0xD8){powerChar->setValue(reinterpret_cast<uint8_t*>(&b),sizeof(b));if(powerCccd->getNotifications())powerChar->notify();}
  lastDiagnostic=millis();
 }
 delay(1);
}
