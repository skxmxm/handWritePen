#include <cstdio>
#include "../../../firmware/Pen_R26_Live/BatteryWindow.h"
int main(){
 BatteryWindow w;w.setOn(true,4,1000,true,4020,970);
 w.sample(1050,3980,1050);w.sample(1100,3740,1100);w.sample(1150,3900,1150);
 w.sample(1200,3950,1200);w.setOn(false,4,1250,false,0,0);
 auto p=makeBatteryDiagnostic(123,w);const auto*b=reinterpret_cast<const uint8_t*>(&p);
 for(unsigned i=0;i<sizeof(p);++i)printf("%02x",b[i]);puts("");
}
