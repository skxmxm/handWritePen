#pragma once
#include <stdint.h>

constexpr const char *PEN_SERVICE="7c7b9001-8e77-4b62-9c3d-4d5d83f4a001";
constexpr const char *PEN_NOTIFY ="7c7b9002-8e77-4b62-9c3d-4d5d83f4a001";
constexpr const char *PEN_CONTROL="7c7b9003-8e77-4b62-9c3d-4d5d83f4a001";
// Framing v3: continuous boot-relative X/Y, including tip-up motion.
// ESP32 little-endian. CRC16-CCITT appended to the complete record.
constexpr uint8_t PEN_WIRE_VERSION=4; // Continuous health/pose; optical samples use their own stream.
struct __attribute__((packed)) PenPacket {
  uint32_t boot,stroke,seq;
  uint64_t t_us,opt_us,imu_us,gsr_us;
  int32_t x,y;
  int16_t angles[3],accel[3],gyro[3]; // 0.01 deg, 0.001 g, 0.1 deg/s
  uint16_t battery_mv;
  int16_t gsr_raw,vex_raw; // ADS1115: 0.125mV/count
  uint16_t flags;
  uint32_t imu_baud,opt_errors;
  uint8_t gsr_state,ads_error,stat1,stat2;
};
static_assert(sizeof(PenPacket)==90,"Packet schema changed");
enum PenFlags:uint16_t {ACTIVE=1,OPT_VALID=2,IMU_VALID=4,ACC_VALID=8,GYRO_VALID=16,
 BAT_VALID=32,ADS_VALID=64,EXC_ON=128,GSR_VALID=256,USB_IN=512,CHARGE_EN=1024,
 TIP_EDGE=2048,RAW_OFF_MODE=4096}; // Raw ADC observation; EXC_ON/GSR_VALID must be clear.
inline uint16_t penCrc(const uint8_t *p,unsigned n){
 uint16_t crc=0xffff;
 while(n--){crc^=uint16_t(*p++)<<8;for(int i=0;i<8;i++)crc=(crc&0x8000)?uint16_t((crc<<1)^0x1021):uint16_t(crc<<1);}
 return crc;
}
