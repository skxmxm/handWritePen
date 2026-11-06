#pragma once
#include <stdint.h>
#include <stddef.h>
#include <vector>
class TwoWire {
 public:
  uint16_t config=0,raw[2]={1234,4000},reply=0;
  bool nack=false,busy=false,wrongConfig=false,shortRead=false;
  int reg=0,left=0;std::vector<uint8_t> tx;
  void beginTransmission(int){tx.clear();}
  void write(uint8_t b){tx.push_back(b);}
  int endTransmission(bool=true){
    if(nack)return 2;
    reg=tx[0];if(tx.size()==3)config=(uint16_t(tx[1])<<8)|tx[2];return 0;
  }
  size_t requestFrom(uint8_t,size_t,bool){
    if(shortRead){left=0;return 0;}
    reply=reg==1 ? (busy?config&0x7fff:config|0x8000) : raw[((config>>12)&7)-4];
    if(reg==1&&wrongConfig)reply^=0x0200;
    left=2;return 2;
  }
  int available(){return left;}
  int read(){return left--==2 ? reply>>8 : reply&255;}
};
