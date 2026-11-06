#include <cstdio>
#include "../../../firmware/Pen_R26_Live/GsrDiagnostic.h"
int main(){
 GsrGate g;
 g.tick(0,true,false,true,true,0,0,0);
 g.tick(100,true,false,true,true,0,0,100);
 g.tick(400,true,false,true,true,0,8,398); // 1 mV at ON settling failure, 2 ms old
 auto p=makeDiagnostic(123,4,g);
 const auto *bytes=reinterpret_cast<const uint8_t*>(&p);
 for(unsigned i=0;i<sizeof(p);++i)printf("%02x",bytes[i]);
 puts("");
}
