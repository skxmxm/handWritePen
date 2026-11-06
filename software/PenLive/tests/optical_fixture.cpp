#include <cstdio>
#include "../../../firmware/Pen_R26_Live/OpticalPacket.h"
int main(){
 OpticalRecord records[]={{0xffffffff,(1ULL<<40),-2048,2047,1,3},
   {0,(1ULL<<40)+5000,-2000,2000,1,3},{1,(1ULL<<40)+10000,-1900,1900,1,6}};
 uint8_t b[OPTICAL_BODY_MAX];unsigned n=packOptical(b,123,200,2,records,3);
 for(unsigned i=0;i<n;++i)printf("%02x",b[i]);puts("");
}
