// Transparent USB <-> FM1828 lidar bridge with lidar power control. Both UARTs run 460800 8N1.
// Lidar TX -> GPIO16, lidar RX <- GPIO17, common GND, lidar VCC 5 V through a high-side switch
// (P-MOSFET module or relay module) whose control input is driven by POWER_PIN (GPIO4, HIGH = lidar on).
// The lidar refuses a new "startlds$" after "stoplds$" until its power is cycled, hence the switch.
// Host escape sequences (never forwarded to the lidar):
//   "\x01PWRCYCLE\x01"  power off 1.5 s, then on      "\x01PWROFF\x01"  power off      "\x01PWRON\x01"  power on
// Everything else is forwarded byte-for-byte in both directions.
#include <Arduino.h>
#ifndef POWER_PIN
#define POWER_PIN 4
#endif
#ifndef POWER_ACTIVE_HIGH
#define POWER_ACTIVE_HIGH 1     // set 0 for switches/relay modules with active-low input
#endif
static const int PIN_RX = 16, PIN_TX = 17;
HardwareSerial lidar(2);
static uint8_t buf[512];

static void lidarPower(bool on) {
  digitalWrite(POWER_PIN, (on == (bool)POWER_ACTIVE_HIGH) ? HIGH : LOW);
  if (!on) {                       // do not back-feed the unpowered lidar through its RX pin
    lidar.end(); pinMode(PIN_TX, OUTPUT); digitalWrite(PIN_TX, LOW);
  } else {
    lidar.begin(460800, SERIAL_8N1, PIN_RX, PIN_TX);
  }
}

// Escape-sequence matcher: holds back bytes while they match a prefix of a known sequence.
static const char* SEQS[] = {"\x01PWRCYCLE\x01", "\x01PWROFF\x01", "\x01PWRON\x01"};
static uint8_t held[16]; static uint8_t heldLen = 0;

static void handleSeq(int which) {
  if (which == 0) { lidarPower(false); delay(1500); lidarPower(true); }
  else if (which == 1) lidarPower(false);
  else lidarPower(true);
}

static void hostByte(uint8_t c) {
  held[heldLen++] = c;
  bool prefix = false;
  for (int k = 0; k < 3; k++) {
    const char* s = SEQS[k]; size_t n = strlen(s);
    if (heldLen <= n && memcmp(held, s, heldLen) == 0) {
      if (heldLen == n) { heldLen = 0; handleSeq(k); return; }
      prefix = true;
    }
  }
  if (!prefix) { lidar.write(held, heldLen); heldLen = 0; }
}

void setup() {
  pinMode(POWER_PIN, OUTPUT);
  Serial.setRxBufferSize(2048);
  Serial.begin(460800);
  lidar.setRxBufferSize(16384);
  lidarPower(true);
}

void loop() {
  int n = lidar.available();
  if (n > 0) { n = lidar.read(buf, n > (int)sizeof(buf) ? sizeof(buf) : n); if (n > 0) Serial.write(buf, n); }
  int m = Serial.available();
  if (m > 0) { m = Serial.read(buf, m > (int)sizeof(buf) ? sizeof(buf) : m); for (int i = 0; i < m; i++) hostByte(buf[i]); }
  if (n <= 0 && m <= 0) delay(1);
}
