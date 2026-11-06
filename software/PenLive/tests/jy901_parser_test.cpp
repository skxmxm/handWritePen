#include <cassert>
#include <cmath>
#include <cstdio>
#include <vector>
#include "../../../firmware/Pen_R26_Live/Jy901Parser.h"

std::vector<uint8_t> frame(uint8_t type,int x,int y,int z) {
  std::vector<uint8_t> b{0x55,type};
  for (int v:{x,y,z,0}) { unsigned u=v<0?v+65536:v;b.push_back(u&255);b.push_back(u>>8); }
  uint8_t sum=0;for (auto v:b)sum+=v;b.push_back(sum);return b;
}
void feed(Jy901Parser &p,const std::vector<uint8_t>& b,uint64_t t) {for (auto x:b)p.feed(x,t);}
int main() {
  Jy901Parser p;
  for (uint8_t b:{0x01,0xff,0x55,0x00})p.feed(b,1);
  feed(p,frame(0x53,16384,-16384,-32768),100);
  assert(p.angle.valid&&p.angle.us==100&&p.frames==1);
  assert(p.angle.v[0]==90&&p.angle.v[1]==-90&&p.angle.v[2]==-180);
  auto broken=frame(0x53,0,0,0);broken[10]^=1;
  feed(p,broken,200);assert(p.angle.us==100&&p.badChecksum==1);
  // Truncated packet immediately followed by a valid frame must resynchronize.
  auto truncated=frame(0x53,12,34,56);truncated.resize(5);feed(p,truncated,300);
  feed(p,frame(0x53,0,0,32767),400);
  assert(p.angle.us==400&&p.angle.v[2]>179.99f);
  feed(p,frame(0x51,2048,-2048,4096),500);
  assert(p.accel.valid&&p.accel.v[0]==1&&p.accel.v[1]==-1&&p.accel.v[2]==2);
  feed(p,frame(0x52,16384,-16384,0),600);
  assert(p.gyro.valid&&p.gyro.v[0]==1000&&p.gyro.v[1]==-1000);
  p.reset();assert(!p.angle.valid&&p.frames==0);
  // Exhaustive signed angle decoding, including payload bytes equal to header.
  for(int raw=-32768;raw<=32767;++raw){
    feed(p,frame(0x53,raw,0,0),700);
    assert(p.angle.valid&&std::fabs(p.angle.v[0]-raw*180.0f/32768)<.00002f);
  }
  puts("PASS: signed angles, accel/gyro scales, checksum rejection, fragmentation, resync, reset.");
}
