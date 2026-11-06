#include <cassert>
#include <cstdio>
#include "../../../firmware/Pen_R26_Live/PenPosition.h"
int main(){
 PenPosition p;
 // Up: move to a starting point; down: write; up: move; down: write again.
 assert(p.add(100,-30));assert(p.x==100&&p.y==-30);
 assert(p.add(20,5));assert(p.x==120&&p.y==-25);
 assert(p.add(50,10));assert(p.x==170&&p.y==-15);
 assert(p.add(-10,-5));assert(p.x==160&&p.y==-20);
 assert(p.add(0,0));assert(p.x==160&&p.y==-20);
 p.x=INT32_MAX;p.y=12;
 assert(!p.add(1,10));assert(p.x==INT32_MAX&&p.y==12);
 p.x=7;p.y=INT32_MIN;
 assert(!p.add(2,-1));assert(p.x==7&&p.y==INT32_MIN);
 assert(p.add(-2,1));assert(p.x==5&&p.y==INT32_MIN+1);
 puts("PASS: continuous optical position and atomic overflow rejection");
}
