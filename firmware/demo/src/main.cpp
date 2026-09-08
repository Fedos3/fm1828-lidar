// Demo for the FM1828 library: prints one line per revolution and the nearest point.
#include <Arduino.h>
#include <FM1828.h>
FM1828 lidar;
static uint16_t nearestMm = 0xFFFF; static float nearestDeg = 0;
void onPoint(float deg, uint16_t mm, bool valid) { if (valid && mm < nearestMm) { nearestMm = mm; nearestDeg = deg; } }
void onScan(uint16_t points, uint16_t speed, uint8_t frames, uint8_t missing) {
  Serial.printf("scan %lu: %u pts, speed=%u, frames=%u, missing=%u, nearest %u mm @ %.2f deg\n",
                (unsigned long)lidar.scans(), points, speed, frames, missing, nearestMm, nearestDeg);
  nearestMm = 0xFFFF;
}
void setup() {
  Serial.begin(115200);
  lidar.begin(Serial2, 16, 17);
  lidar.setPowerPin(4);           // optional 5 V high-side switch; harmless if not wired
  lidar.setPointCallback(onPoint); lidar.setScanCallback(onScan);
  delay(500);
  Serial.println("FM1828 demo: sending $ then startlds$");
  lidar.start();
}
void loop() {
  lidar.loop();
  if (Serial.available()) { int c = Serial.read(); if (c == 'r') { Serial.println("restart: power cycle + start"); lidar.restart(); } else if (c == 'x') lidar.stop(); }
  static uint32_t t = 0;
  if (millis() - t > 2000 && !lidar.isSpinning()) { t = millis(); Serial.printf("idle: dist=%u mm, idle frames=%lu, ack=%d\n", lidar.idleDistanceMm(), (unsigned long)lidar.idleFrames(), lidar.ackSeen()); }
}
