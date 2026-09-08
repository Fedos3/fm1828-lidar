#include "FM1828.h"

void FM1828::begin(Stream& stream) { stream_ = &stream; len_ = 0; lastIdx_ = -1; }

void FM1828::begin(HardwareSerial& serial, int rxPin, int txPin) {
  hw_ = &serial; rxPin_ = rxPin; txPin_ = txPin;
  serial.setRxBufferSize(8192);
  serial.begin(BAUD, SERIAL_8N1, rxPin, txPin);
  begin((Stream&)serial);
}

void FM1828::setPowerPin(int pin, bool activeHigh) {
  powerPin_ = pin; powerActiveHigh_ = activeHigh;
  pinMode(pin, OUTPUT);
  powerOn();
}

void FM1828::powerOn() {
  if (powerPin_ < 0) return;
  digitalWrite(powerPin_, powerActiveHigh_ ? HIGH : LOW);
  if (hw_) hw_->begin(BAUD, SERIAL_8N1, rxPin_, txPin_);
  len_ = 0; lastIdx_ = -1; startPending_ = false;
}

void FM1828::powerOff() {
  if (powerPin_ < 0) return;
  startPending_ = false;
  if (hw_) { hw_->end(); pinMode(txPin_, OUTPUT); digitalWrite(txPin_, LOW); }  // no back-feed through lidar RX
  digitalWrite(powerPin_, powerActiveHigh_ ? LOW : HIGH);
}

void FM1828::restart() {
  powerOff(); delay(1500); powerOn(); delay(2500); start();
}

void FM1828::sendRaw(const char* s) { if (stream_) { stream_->write((const uint8_t*)s, strlen(s)); stream_->flush(); } }

// Robot-like start: "startldspl$" first; if no frames within 3 s, loop() sends "$" and then "startlds$".
void FM1828::start() { sendRaw("startldspl$"); startPending_ = true; startAtMs_ = millis() + 3000; startFramesRef_ = framesOk_; }

void FM1828::stop() { startPending_ = false; sendRaw("stoplds$"); }

void FM1828::handleFrame(const uint8_t* f) {
  uint8_t idx = f[1];
  speed_ = f[2] | (f[3] << 8);
  lastFrameMs_ = millis();
  if (lastIdx_ >= 0) {
    if (idx < lastIdx_) {  // wrapped -> revolution complete
      ++scans_;
      if (scanCb_) scanCb_(scanPoints_, speed_, scanFrames_, scanMissing_);
      scanPoints_ = 0; scanFrames_ = 0; scanMissing_ = 0;
    } else if (idx - lastIdx_ > 1) {
      scanMissing_ += idx - lastIdx_ - 1;
    }
  }
  lastIdx_ = idx;
  ++scanFrames_;
  for (uint8_t j = 0; j < POINTS_PER_FRAME; j++) {
    uint16_t d = f[4 + 2 * j] | (f[5 + 2 * j] << 8);
    bool valid = d > 0 && d < MAX_VALID_MM;
    if (valid) ++scanPoints_;
    if (pointCb_) pointCb_(angleOf(idx, j), d, valid);
  }
}

void FM1828::loop() {
  if (!stream_) return;
  if (startPending_ && (int32_t)(millis() - startAtMs_) >= 0) {
    startPending_ = false;
    if (framesOk_ == startFramesRef_) { sendRaw("$"); fallbackPending_ = true; fallbackAtMs_ = millis() + 2000; }
  }
  if (fallbackPending_ && (int32_t)(millis() - fallbackAtMs_) >= 0) { fallbackPending_ = false; sendRaw("startlds$"); }
  while (stream_->available() > 0) {
    int c = stream_->read();
    if (c < 0) break;
    if (len_ == 0) {
      if (c == 0xFA || c == 0x5A) buf_[len_++] = c;
      else if (c == 0x21) ackSeen_ = true;
      continue;
    }
    buf_[len_++] = c;
    if (buf_[0] == 0x5A) {
      if (len_ == 2 && buf_[1] != 0xA5) { len_ = 0; if (c == 0xFA || c == 0x5A) buf_[len_++] = c; continue; }
      if (len_ == 4) { ++idleFrames_; idleMm_ = (buf_[2] << 8) | buf_[3]; len_ = 0; }
      continue;
    }
    if (len_ == FRAME_LEN) {
      uint16_t sum = 0; for (uint8_t i = 0; i < 60; i++) sum += buf_[i];
      uint16_t cs = buf_[60] | (buf_[61] << 8);
      if (sum == cs && buf_[1] >= IDX_FIRST && buf_[1] <= IDX_LAST) { ++framesOk_; handleFrame(buf_); len_ = 0; }
      else {
        ++framesBad_;
        // resync: shift to the next candidate header inside the buffer
        uint8_t k = 1; while (k < len_ && buf_[k] != 0xFA && buf_[k] != 0x5A) k++;
        len_ -= k; memmove(buf_, buf_ + k, len_);
      }
    }
  }
}
