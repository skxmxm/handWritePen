#pragma once
#include <stdint.h>
#include <limits.h>

// Continuous optical coordinates; tip state only controls ink, never displacement.
class PenPosition {
 public:
  int32_t x=0,y=0;
  bool add(int16_t dx,int16_t dy){
    int64_t nx=int64_t(x)+dx,ny=int64_t(y)+dy;
    if(nx<INT32_MIN||nx>INT32_MAX||ny<INT32_MIN||ny>INT32_MAX)return false;
    x=int32_t(nx);y=int32_t(ny);return true;
  }
};
