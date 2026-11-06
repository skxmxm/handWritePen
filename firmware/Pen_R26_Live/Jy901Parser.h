#pragma once
#include <stdint.h>
#include <string.h>

// WIT standard UART: 0x55, type, 8 payload bytes, sum(first 10) & 0xff.
// No sensor register writes, calibration, baud changes or EEPROM writes.
class Jy901Parser {
 public:
  struct Reading { float v[3] = {}; uint64_t us = 0; bool valid = false; };
  Reading angle, accel, gyro;
  uint32_t frames = 0, badChecksum = 0;
  uint64_t lastFrameUs = 0;
  void reset() { *this = Jy901Parser(); }
  bool feed(uint8_t b, uint64_t now) {
    if (!used_ && b != 0x55) return false;
    bytes_[used_++] = b;
    if (used_ == 2 && (bytes_[1] < 0x50 || bytes_[1] > 0x5F)) {
      bytes_[0] = b; used_ = b == 0x55 ? 1 : 0;
      return false;
    }
    if (used_ < 11) return false;
    uint8_t sum = 0;
    for (int i = 0; i < 10; ++i) sum += bytes_[i];
    if (sum != bytes_[10]) {
      ++badChecksum;
      // Slide to the next possible header instead of discarding a whole frame.
      unsigned start = 1;
      while (start < 11 && bytes_[start] != 0x55) ++start;
      used_ = 11 - start;
      memmove(bytes_, bytes_ + start, used_);
      return false;
    }
    used_ = 0; ++frames; lastFrameUs = now;
    Reading *r = nullptr; float scale = 0;
    if (bytes_[1] == 0x51) { r = &accel; scale = 16.0f / 32768.0f; }
    if (bytes_[1] == 0x52) { r = &gyro; scale = 2000.0f / 32768.0f; }
    if (bytes_[1] == 0x53) { r = &angle; scale = 180.0f / 32768.0f; }
    if (r) {
      for (int i = 0; i < 3; ++i) {
        const uint16_t raw = uint16_t(bytes_[2+i*2]) | (uint16_t(bytes_[3+i*2]) << 8);
        const int32_t value = raw >= 32768 ? int32_t(raw) - 65536 : raw;
        r->v[i] = value * scale;
      }
      r->us = now; r->valid = true;
    }
    return true;
  }
 private:
  uint8_t bytes_[11] = {};
  unsigned used_ = 0;
};
