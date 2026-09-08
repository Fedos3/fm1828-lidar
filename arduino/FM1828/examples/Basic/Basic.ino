#include <FM1828.h>
FM1828 lidar;
void onScan(uint16_t points, uint16_t speed, uint8_t frames, uint8_t missing) {
  Serial.printf("scan: %u points, speed=%u, frames=%u, missing=%u\n", points, speed, frames, missing);
}
void setup() {
  Serial.begin(115200);
  lidar.begin(Serial2, 16, 17);   // lidar TX -> GPIO16, lidar RX <- GPIO17
  lidar.setScanCallback(onScan);
  delay(500);
  lidar.start();                  // "$" now, "startlds$" after 2 s
}
void loop() { lidar.loop(); }
