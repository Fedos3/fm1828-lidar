// Ecovacs-style probe / raw dump for the Ecovacs FM1828 lidar (DEEBOT T8/T9/N8 Pro dToF LDS unit).
// Verified on 2026-09-08: FM1828 speaks the Ecovacs LDS-006 command protocol at 460800 8N1:
//   "$"          -> lidar replies 0x21, then streams idle frames 5A A5 <dist_hi> <dist_lo> (mm, big endian)
//   "startlds$"  -> lidar spins its own motor (no external PWM) and streams 0xFA frames
//   "stoplds$"   -> stream returns to idle frames
// Wiring: lidar TX -> GPIO16 (RX), lidar RX -> GPIO17 (TX), common GND, lidar VCC = 5 V.
// USB console runs at 460800 so raw lidar traffic can be forwarded without loss.
// USB commands: 'g' = probe sequence at 460800, 'i' = "$" + 3 s raw dump, 'd' = "$" 2 s + "startlds$" + 15 s raw dump (one UART session, no ESP32 reset in between)
// + "stoplds$" + 3 s raw dump, 'x' = "stoplds$" + 2 s raw dump, ':text' = send text at manual baud, ':b<baud>'.
#include <Arduino.h>
HardwareSerial lidar(2);
static const int PIN_RX = 16, PIN_TX = 17;
static const uint32_t LIDAR_BAUD = 460800;
volatile uint32_t edges = 0;
uint32_t rxCount; uint8_t sample[160]; size_t kept;
void IRAM_ATTR onEdge() { ++edges; }

void listen(uint32_t ms) {
  uint32_t t = millis();
  while (millis() - t < ms) {
    int c;
    while ((c = lidar.read()) >= 0) { ++rxCount; if (kept < sizeof(sample)) sample[kept++] = c; }
    delay(1);
  }
}
void report(const char* name, uint32_t baud) {
  Serial.printf("RESULT %s baud=%lu RX=%lu edges=%lu line=%s HEX=", name, (unsigned long)baud,
                (unsigned long)rxCount, (unsigned long)edges, digitalRead(PIN_RX) ? "HIGH" : "LOW");
  for (size_t i = 0; i < kept; i++) Serial.printf("%02X ", sample[i]);
  Serial.print(" ASCII=");
  for (size_t i = 0; i < kept; i++) Serial.print((sample[i] >= 32 && sample[i] < 127) ? (char)sample[i] : '.');
  Serial.println(); Serial.flush();
}
void reset() { rxCount = 0; kept = 0; edges = 0; while (lidar.read() >= 0) {} }
void send(const char* name, const uint8_t* p, size_t n, uint32_t baud, uint32_t listenMs) {
  reset();
  Serial.printf("BEGIN %s baud=%lu TX=", name, (unsigned long)baud);
  for (size_t i = 0; i < n; i++) Serial.printf("%02X ", p[i]);
  Serial.println();
  lidar.write(p, n); lidar.flush();
  listen(listenMs);
  report(name, baud);
}
void sendStr(const char* name, const char* s, uint32_t baud, uint32_t listenMs) {
  send(name, (const uint8_t*)s, strlen(s), baud, listenMs);
}
void openLidar(uint32_t baud) {
  lidar.begin(baud, SERIAL_8N1, PIN_RX, PIN_TX);
  attachInterrupt(digitalPinToInterrupt(PIN_RX), onEdge, CHANGE);
}
void closeLidar() { detachInterrupt(digitalPinToInterrupt(PIN_RX)); lidar.end(); pinMode(PIN_TX, OUTPUT); digitalWrite(PIN_TX, HIGH); } // keep lidar RX at UART idle level, never floating
void runSequence() {
  const uint32_t bauds[] = {460800}; // other bauds removed: junk at wrong baud may have wedged the lidar command parser
  for (uint32_t baud : bauds) {
    openLidar(baud);
    bool primary = (baud == LIDAR_BAUD);
    reset(); listen(primary ? 1500 : 500); report("IDLE", baud);
    sendStr("DOLLAR", "$", baud, primary ? 3000 : 1500);
    sendStr("STARTLDS", "startlds$", baud, primary ? 8000 : 3000);
    sendStr("STARTLDS_CRLF", "startlds$\r\n", baud, primary ? 4000 : 1500);
    sendStr("STOPLDS", "stoplds$", baud, 1500);
    sendStr("DOLLAR_AGAIN", "$", baud, 1500);
    closeLidar();
    delay(200);
  }
  Serial.println("ECOVACS PROBE COMPLETE");
}
// Raw dump: forward every lidar byte to USB verbatim between text markers.
void rawDump(const char* name, const char* cmd, uint32_t ms) {
  while (lidar.read() >= 0) {}
  Serial.printf("\nDUMP BEGIN %s cmd=%s ms=%lu\n", name, cmd, (unsigned long)ms); Serial.flush();
  if (cmd[0]) { lidar.write((const uint8_t*)cmd, strlen(cmd)); lidar.flush(); }
  uint32_t t = millis(), n = 0; uint8_t buf[256];
  while (millis() - t < ms) {
    int avail = lidar.available();
    if (avail > 0) { int k = lidar.read(buf, avail > (int)sizeof(buf) ? sizeof(buf) : avail); if (k > 0) { Serial.write(buf, k); n += k; } }
    else delay(1);
  }
  Serial.printf("\nDUMP END %s bytes=%lu\n", name, (unsigned long)n); Serial.flush();
}
uint32_t manualBaud = LIDAR_BAUD; bool manualOpen = false;
void manual(String line) {
  line.trim();
  if (line.startsWith(":b")) { manualBaud = line.substring(2).toInt(); if (manualOpen) closeLidar(); manualOpen = false; Serial.printf("MANUAL baud=%lu\n", (unsigned long)manualBaud); return; }
  if (!manualOpen) { openLidar(manualBaud); manualOpen = true; }
  String s = line.substring(1); s.replace("\\n", "\n"); s.replace("\\r", "\r");
  send("MANUAL", (const uint8_t*)s.c_str(), s.length(), manualBaud, 3000);
}
void setup() {
  Serial.begin(460800); lidar.setRxBufferSize(16384); pinMode(PIN_TX, OUTPUT); digitalWrite(PIN_TX, HIGH);
  delay(1000);
  Serial.println("READY: FM1828 probe. g=multi-baud sequence, i=$ dump 3s, d=$ dump 2s + startlds$ dump 15s + stoplds$ dump 3s (one session), s=startlds$ only + stoplds$, n=$ / startlds$ / $ / startlds$ / stoplds$ / startlds$ (restart test), x=stoplds$ dump 2s, ':text' manual, ':b<baud>'");
}
void loop() {
  static String buf;
  int c = Serial.read();
  if (c < 0) { delay(5); return; }
  if (buf.length() == 0) {
    if (c == 'g') { runSequence(); return; }
    if (c == 'i') { openLidar(LIDAR_BAUD); rawDump("IDLE", "$", 3000); closeLidar(); Serial.println("DONE i"); return; }
    if (c == 'd') { openLidar(LIDAR_BAUD); rawDump("DOLLAR", "$", 2000); rawDump("START", "startlds$", 15000); rawDump("STOP", "stoplds$", 3000); closeLidar(); Serial.println("DONE d"); return; }
    if (c == 'n') { openLidar(LIDAR_BAUD); rawDump("DOLLAR", "$", 2000); rawDump("START", "startlds$", 8000); rawDump("DOLLAR2", "$", 5000); rawDump("START2", "startlds$", 8000); rawDump("STOP", "stoplds$", 3000); rawDump("START3", "startlds$", 6000); closeLidar(); Serial.println("DONE n"); return; }
    if (c == 's') { openLidar(LIDAR_BAUD); rawDump("START", "startlds$", 15000); rawDump("STOP", "stoplds$", 3000); closeLidar(); Serial.println("DONE s"); return; }
    if (c == 'x') { openLidar(LIDAR_BAUD); rawDump("STOP", "stoplds$", 2000); closeLidar(); Serial.println("DONE x"); return; }
  }
  if (c == '\n' || c == '\r') { if (buf.startsWith(":")) manual(buf); buf = ""; return; }
  buf += (char)c;
}
