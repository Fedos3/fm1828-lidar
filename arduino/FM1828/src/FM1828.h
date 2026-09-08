#pragma once
#include <Arduino.h>

// Ecovacs FM1828 dToF lidar driver (protocol verified 2026-09-08).
// UART 460800 8N1, 3.3 V. Commands: "$" (ack 0x21 once after power-on, then idle frames),
// "startlds$" (motor on, scan frames), "stoplds$" (motor off, idle frames).
// Scan frame: FA idx speed(u16) dist[16](u16 mm) tail[24] sum16 -> 90 frames x 16 points = 1440 points / rev.
// Note: "startlds$" as the very first command after opening the UART is ignored; send "$" first (start() does this).
// Note: after "stoplds$" the lidar did not accept a new start until power-cycled (observed twice).
class FM1828 {
 public:
  static const uint32_t BAUD = 460800;
  static const uint8_t FRAME_LEN = 62, IDX_FIRST = 0xA0, IDX_LAST = 0xF9, FRAMES_PER_REV = 90, POINTS_PER_FRAME = 16;
  static const uint16_t MAX_VALID_MM = 32000;

  typedef void (*PointCallback)(float angle_deg, uint16_t distance_mm, bool valid);
  typedef void (*ScanCallback)(uint16_t valid_points, uint16_t speed, uint8_t frames, uint8_t missing_frames);

  // Stream must already be open at 460800 8N1 (e.g. Serial2.begin(FM1828::BAUD, SERIAL_8N1, 16, 17)).
  void begin(Stream& stream);
  // Convenience: opens the HardwareSerial on the given pins.
  void begin(HardwareSerial& serial, int rxPin, int txPin);

  // Optional 5 V high-side switch for the lidar (P-MOSFET or relay module). Needed to restart after stop().
  void setPowerPin(int pin, bool activeHigh = true);
  void powerOn();
  void powerOff();
  void restart();        // blocking ~4 s: power off 1.5 s, power on, settle, then start()

  void start();          // non-blocking: sends "$", then "startlds$" 2 s later from loop()
  void stop();           // sends "stoplds$"
  void sendRaw(const char* s);
  void loop();           // call often: parses incoming bytes, fires callbacks

  void setPointCallback(PointCallback cb) { pointCb_ = cb; }
  void setScanCallback(ScanCallback cb) { scanCb_ = cb; }

  bool isSpinning() const { return lastFrameMs_ && (millis() - lastFrameMs_) < 500; }
  uint16_t speed() const { return speed_; }
  uint16_t idleDistanceMm() const { return idleMm_; }
  uint32_t framesOk() const { return framesOk_; }
  uint32_t framesBad() const { return framesBad_; }
  uint32_t idleFrames() const { return idleFrames_; }
  uint32_t scans() const { return scans_; }
  bool ackSeen() const { return ackSeen_; }

  static float angleOf(uint8_t idx, uint8_t point) { return (idx - IDX_FIRST) * 4.0f + point * 0.25f; }

 private:
  void handleFrame(const uint8_t* f);
  Stream* stream_ = nullptr;
  HardwareSerial* hw_ = nullptr; int rxPin_ = -1, txPin_ = -1, powerPin_ = -1; bool powerActiveHigh_ = true;
  uint8_t buf_[128]; uint8_t len_ = 0;
  uint32_t framesOk_ = 0, framesBad_ = 0, idleFrames_ = 0, scans_ = 0, lastFrameMs_ = 0, startAtMs_ = 0;
  uint16_t speed_ = 0, idleMm_ = 0, scanPoints_ = 0;
  uint8_t scanFrames_ = 0, scanMissing_ = 0;
  int lastIdx_ = -1;
  bool ackSeen_ = false, startPending_ = false;
  PointCallback pointCb_ = nullptr; ScanCallback scanCb_ = nullptr;
};
