/*
 * R26 ESP32-S3 / J402 normally-open pen-tip switch test.
 * J402.1 = TIP_RAW -> R412 (1k) -> GPIO11; J402.2 = GND.
 * R411 (10k) supplies the external pull-up: released HIGH, pressed LOW.
 * No external library. USB CDC serial at 115200 baud.
 * Disconnect the battery while its reported heating fault is unresolved.
 */
#include <Arduino.h>

#if !defined(CONFIG_IDF_TARGET_ESP32S3)
#error "Select ESP32S3 Dev Module."
#endif
#if !ARDUINO_USB_CDC_ON_BOOT || !ARDUINO_USB_MODE
#error "Enable USB CDC On Boot; select Hardware CDC and JTAG for USB Mode."
#endif

constexpr uint8_t TIP_PIN = 11;
constexpr uint8_t SYS_LED = 12, FAULT_LED = 13;
constexpr uint8_t GSR_EN = 7, CHG_EN = 21, BAT_SENSE_EN = 48;
constexpr uint32_t DEBOUNCE_MS = 10, REPORT_MS = 200;

int rawLevel = HIGH;
int stableLevel = -1; // Not initialized until the input stays stable for 10 ms.
uint32_t lastRawChange = 0, lastReport = 0;
uint32_t pressCount = 0, releaseCount = 0;
bool liveOutput = true, serialWasOpen = false;

const char *switchState() {
  if (stableLevel < 0) return "WAIT";
  return stableLevel == LOW ? "PRESSED" : "RELEASED";
}

void printState() {
  if (!Serial) return;
  Serial.printf("RAW:%d\tTIP:%d\tPRESS:%lu\tRELEASE:%lu\tSTATE:%s\n",
                rawLevel, stableLevel < 0 ? -1 : (stableLevel == LOW ? 1 : 0),
                (unsigned long)pressCount, (unsigned long)releaseCount, switchState());
}

void printHelp() {
  if (!Serial) return;
  Serial.println("\n# R26 pen-tip switch: J402.1=TIP/GPIO11, J402.2=GND.");
  Serial.println("# Normally open contact only. Released RAW=1; pressed RAW=0.");
  Serial.printf("# Debounce=%lu ms; RAW is sampled level, TIP is debounced pressed state.\n",
                (unsigned long)DEBOUNCE_MS);
  Serial.println("# h help | s status | l live output on/off | z zero counters");
  Serial.println("# SYS LED follows debounced press. Startup state is not counted as an event.");
  Serial.println("# USB only for this test; disconnect faulty battery. Charging/GSR disabled.");
  printState();
}

void updateSwitch(uint32_t now, int sampledLevel) {
  if (sampledLevel != rawLevel) {
    rawLevel = sampledLevel;
    lastRawChange = now;
  }
  if (rawLevel == stableLevel || uint32_t(now - lastRawChange) < DEBOUNCE_MS) return;

  const bool initial = stableLevel < 0;
  stableLevel = rawLevel;
  if (!initial) {
    if (stableLevel == LOW) ++pressCount;
    else ++releaseCount;
  }
  digitalWrite(SYS_LED, stableLevel == LOW ? HIGH : LOW);
  if (liveOutput && Serial) {
    Serial.printf("# %s %s at %lu ms\n", initial ? "INITIAL" : "EVENT",
                  switchState(), (unsigned long)now);
    printState();
  }
}

void handleCommand(char command) {
  switch (command) {
    case 'h': printHelp(); break;
    case 's': printState(); break;
    case 'l':
      liveOutput = !liveOutput;
      if (Serial) Serial.printf("# Live output %s; sampling and counters continue.\n",
                                liveOutput ? "ON" : "OFF");
      break;
    case 'z':
      pressCount = releaseCount = 0;
      if (Serial) Serial.println("# Counters reset; current switch state unchanged.");
      printState();
      break;
    default: break; // Ignore CR/LF and unknown characters.
  }
}

void setup() {
  const uint8_t outputs[] = {GSR_EN, CHG_EN, BAT_SENSE_EN, SYS_LED, FAULT_LED};
  for (uint8_t pin : outputs) {
    digitalWrite(pin, LOW);
    pinMode(pin, OUTPUT);
  }
  pinMode(TIP_PIN, INPUT); // Use fitted R411; do not mask a missing pull-up with software.
  Serial.begin(115200);
  Serial.setTxTimeoutMs(10);
  const uint32_t start = millis();
  while (!Serial && uint32_t(millis() - start) < 1200) delay(10);
  rawLevel = digitalRead(TIP_PIN);
  lastRawChange = lastReport = millis();
  serialWasOpen = bool(Serial);
  printHelp();
}

void loop() {
  updateSwitch(millis(), digitalRead(TIP_PIN));
  const bool connected = bool(Serial);
  if (connected && !serialWasOpen) printHelp();
  serialWasOpen = connected;
  if (Serial.available()) handleCommand(char(Serial.read()));
  const uint32_t now = millis();
  if (uint32_t(now - lastReport) >= REPORT_MS) {
    lastReport = now;
    if (liveOutput) printState();
  }
  delay(1);
}
