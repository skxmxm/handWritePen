#pragma once
#include <stdint.h>
#include "BlePacket.h"
#include "GsrGate.h"
constexpr const char *PEN_DIAGNOSTIC="7c7b9004-8e77-4b62-9c3d-4d5d83f4a001";
// Separate optional characteristic: 20 bytes fits MTU=23; main v2 packet unchanged.
struct __attribute__((packed)) GsrDiagnostic {
 uint8_t magic,version;
 uint32_t boot,stroke;
 uint8_t reason,phase,flags,adc;
 int16_t vex;
 uint16_t age,crc;
};
static_assert(sizeof(GsrDiagnostic)==20,"Diagnostic packet size");
inline GsrDiagnostic makeDiagnostic(uint32_t boot,uint32_t faultStroke,const GsrGate &g){
 GsrDiagnostic p={};p.magic=0xD7;p.version=1;p.boot=boot;p.stroke=faultStroke;
 p.reason=g.reason;p.phase=g.faultPhase;p.flags=g.faultValid?1:0;p.adc=g.faultAdc;
 p.vex=g.faultVex;p.age=g.faultAge;p.crc=penCrc(reinterpret_cast<const uint8_t*>(&p),18);
 return p;
}
