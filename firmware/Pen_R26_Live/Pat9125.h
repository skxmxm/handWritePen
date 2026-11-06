#pragma once
#include <Arduino.h>
#include <Wire.h>

// Minimal PAT9125EL diagnostic driver. Register definitions were cross-checked
// against Zephyr input_pat912x, modm and Prusa's PAT9125 driver. No unpublished
// bank-1 tracking tuning is applied. This is not a calibrated pen driver.
class Pat9125 {
 public:
  struct Motion { uint8_t status; int16_t dx, dy; };
  struct Error { const char *operation; uint8_t reg, code; };
  static constexpr uint8_t RESOLUTION = 100; // 5 counts/inch per step: 500 CPI.
  explicit Pat9125(TwoWire &bus, uint8_t address = 0x75)
      : bus_(bus), address_(address) {}

  bool ready() const { return ready_; }
  const Error &error() const { return error_; }
  void stop() { ready_ = false; }

  static int16_t signed12(uint16_t raw) {
    raw &= 0x0FFF;
    return (raw & 0x0800) ? int16_t(int32_t(raw) - 4096) : int16_t(raw);
  }

  bool read(uint8_t reg, uint8_t *out, uint8_t length = 1) {
    if (length == 0 || length > 4) return fail("length", reg, 0xE0);
    bus_.beginTransmission(address_);
    bus_.write(reg);
    const uint8_t code = bus_.endTransmission(false);
    if (code) return fail("address/read", reg, code);
    const size_t count = bus_.requestFrom(address_, size_t(length), true);
    if (count != length || bus_.available() < length) {
      while (bus_.available()) bus_.read();
      return fail("short-read", reg, 0xE1);
    }
    uint8_t temp[4];
    for (uint8_t i = 0; i < length; ++i) temp[i] = uint8_t(bus_.read());
    for (uint8_t i = 0; i < length; ++i) out[i] = temp[i];
    return true;
  }

  bool identity(uint8_t &id1, uint8_t &id2) {
    uint8_t ids[2];
    if (!read(0x00, ids, 2)) return false;
    id1 = ids[0]; id2 = ids[1];
    return true;
  }

  bool begin() {
    ready_ = false;
    resetNack_ = false;
    error_ = {"none", 0, 0};
    uint8_t id1, id2;
    // Do not write reset/configuration to an unidentified device.
    if (!identity(id1, id2)) return false;
    if (id1 != 0x31 || id2 != 0x91) return fail("product-id", 0x00, 0xE2);

    // This reset can NACK while the device restarts. Other bus failures are
    // not ignored, and successful post-reset reads are still mandatory.
    if (!write(0x06, 0x97)) {
      if (error_.code != 2 && error_.code != 3) return false;
      resetNack_ = true;
    }
    delay(10);
    if (!write(0x7F, 0x00) || !write(0x06, 0x17)) return false;
    if (!identity(id1, id2)) return false;
    if (id1 != 0x31 || id2 != 0x91) return fail("post-reset-id", 0x00, 0xE2);
    if (!write(0x09, 0x5A)) return false;

    uint8_t mode = 0;
    bool ok = read(0x05, &mode);
    if (ok) ok = setChecked(0x05, mode & uint8_t(~0x18)); // Disable auto sleep for test.
    if (ok) ok = setChecked(0x0D, RESOLUTION);
    if (ok) ok = setChecked(0x0E, RESOLUTION);
    if (ok) ok = setChecked(0x19, 0x04); // 12-bit X/Y, no axis swap or inversion.
    if (!ok) {
      const Error saved = error_;
      write(0x09, 0x00); // Best-effort restore write protection.
      error_ = saved;
      return false;
    }
    if (!write(0x09, 0x00)) return false;
    delay(10);
    error_ = {"none", 0, 0};
    ready_ = true;
    return true;
  }

  bool resetNacked() const { return resetNack_; }

  bool poll(Motion &out) {
    if (!ready_) return fail("not-ready", 0, 0xE3);
    Motion sample = {};
    if (!read(0x02, &sample.status)) return false;
    if (sample.status & 0x80) {
      uint8_t low[2], high;
      // Read status, both low bytes, then the shared high-nibble register.
      // Commit neither axis if any transfer failed.
      if (!read(0x03, low, 2) || !read(0x12, &high)) return false;
      sample.dx = signed12(uint16_t(low[0]) | (uint16_t(high & 0xF0) << 4));
      sample.dy = signed12(uint16_t(low[1]) | (uint16_t(high & 0x0F) << 8));
    }
    out = sample; // Valid no-motion result is zero; a failed read is not.
    return true;
  }

 private:
  bool fail(const char *operation, uint8_t reg, uint8_t code) {
    error_ = {operation, reg, code};
    return false;
  }
  bool write(uint8_t reg, uint8_t value) {
    bus_.beginTransmission(address_);
    bus_.write(reg); bus_.write(value);
    const uint8_t code = bus_.endTransmission(true);
    return code == 0 || fail("write", reg, code);
  }
  bool setChecked(uint8_t reg, uint8_t value) {
    uint8_t actual;
    if (!write(reg, value) || !read(reg, &actual)) return false;
    return actual == value || fail("readback", reg, 0xE4);
  }
  TwoWire &bus_;
  const uint8_t address_;
  bool ready_ = false, resetNack_ = false;
  Error error_ = {"none", 0, 0};
};
