#pragma once
#include <stdint.h>
#include <string.h>
#include "BlePacket.h"
constexpr const char *PEN_OPTICAL="7c7b9006-8e77-4b62-9c3d-4d5d83f4a001";
enum OpticalFlags:uint8_t {PEN_DOWN=1,MOTION_VALID=2,TIP_BOUNDARY=4};
struct __attribute__((packed)) OpticalRecord {
 uint32_t seq; uint64_t t_us; int32_t x,y; uint32_t stroke; uint8_t flags;
};
struct __attribute__((packed)) OpticalHeader {
 uint32_t boot,acquired,dropped; uint8_t count;
};
constexpr unsigned OPTICAL_BATCH_MAX=6;
constexpr unsigned OPTICAL_BODY_MAX=sizeof(OpticalHeader)+OPTICAL_BATCH_MAX*sizeof(OpticalRecord)+2;
static_assert(sizeof(OpticalRecord)==25&&sizeof(OpticalHeader)==13,"Optical wire layout");
static_assert(OPTICAL_BODY_MAX<=176,"One large-MTU fragment per batch");
inline unsigned packOptical(uint8_t *out,uint32_t boot,uint32_t acquired,uint32_t dropped,
                            const OpticalRecord *records,unsigned count){
 if(!count||count>OPTICAL_BATCH_MAX)return 0;
 OpticalHeader h={boot,acquired,dropped,uint8_t(count)};
 memcpy(out,&h,sizeof(h));memcpy(out+sizeof(h),records,count*sizeof(*records));
 unsigned n=sizeof(h)+count*sizeof(*records);uint16_t crc=penCrc(out,n);
 out[n]=crc&255;out[n+1]=crc>>8;return n+2;
}
