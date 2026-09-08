"""Serial driver for the FM1828 through the ESP32 transparent bridge (firmware/bridge), plus a replay source."""
import re
import threading
import time
from typing import Callable, Optional

from .protocol import StreamParser, Scan, FRAME_LEN

BAUD = 460800
CMD_ACK = b'$'
CMD_START = b'startlds$'
CMD_START_PLUS = b'startldspl$'   # "plus startup" from the DEEBOT firmware; alone it only test-spins for a few seconds
CMD_STOP = b'stoplds$'
START_DELAY_S = 2.0   # "$" first, then startlds$ after this delay: startlds$ alone as the first command is ignored
# Escape sequences understood by firmware/bridge (need a 5 V high-side switch on GPIO4); never reach the lidar.
BRIDGE_PWRCYCLE = b'\x01PWRCYCLE\x01'
BRIDGE_PWROFF = b'\x01PWROFF\x01'
BRIDGE_PWRON = b'\x01PWRON\x01'
POWER_SETTLE_S = 2.5


class SerialSource:
    """Serial port to the ESP32 bridge. Reopens the port automatically if the USB device drops and comes back."""

    def __init__(self, port: str, baud: int = BAUD):
        self.port, self.baud = port, baud
        self._ser = None
        self.reconnects = 0
        self.last_error = None
        self._open()

    def _open(self):
        import serial
        s = serial.Serial()
        s.port, s.baudrate, s.timeout = self.port, self.baud, 0.05
        s.dtr = False   # do not reset the ESP32 on open
        s.rts = False
        s.open()
        self._ser = s

    def _reopen(self, err):
        self.last_error = f'{type(err).__name__}: {err}'
        try:
            if self._ser:
                self._ser.close()
        except Exception:
            pass
        self._ser = None
        time.sleep(0.5)
        try:
            self._open()
            self.reconnects += 1
        except Exception as e:
            self.last_error = f'reopen failed: {e}'

    def read(self) -> bytes:
        if self._ser is None:
            self._reopen(RuntimeError('port closed'))
            return b''
        try:
            n = self._ser.in_waiting
            return self._ser.read(n if n > 0 else 1)
        except Exception as e:
            self._reopen(e)
            return b''

    def write(self, data: bytes):
        if self._ser is None:
            raise RuntimeError('serial port not open: ' + str(self.last_error))
        self._ser.write(data)
        self._ser.flush()

    def close(self):
        if self._ser:
            self._ser.close()


class ReplaySource:
    """Replays a raw capture (e.g. captures/fm1828-spin-onesession.bin) at roughly real time and loops."""

    def __init__(self, path: str, bytes_per_second: float = 28000.0, loop: bool = True):
        data = open(path, 'rb').read()
        # strip the text markers written by the probe firmware / capture.py
        data = re.sub(rb'\n?DUMP (BEGIN|END) [^\n]*\n', b'', data)
        data = re.sub(rb'READY:[^\n]*\n', b'', data)
        data = re.sub(rb'DONE [a-z]\n', b'', data)
        self._data = data
        self._pos = 0
        self._bps = bytes_per_second
        self._loop = loop
        self._t0 = time.monotonic()
        self._sent = 0
        self.spinning = False

    def read(self) -> bytes:
        if not self.spinning:
            time.sleep(0.05)
            return b''
        budget = int((time.monotonic() - self._t0) * self._bps) - self._sent
        if budget <= 0:
            time.sleep(0.005)
            return b''
        chunk = self._data[self._pos:self._pos + budget]
        self._pos += len(chunk)
        self._sent += len(chunk)
        if self._pos >= len(self._data):
            if not self._loop:
                self.spinning = False
            self._pos = 0
        return chunk

    def write(self, data: bytes):
        if data in (CMD_START, CMD_START_PLUS):
            self.spinning = True
            self._t0, self._sent = time.monotonic(), 0
        elif data in (CMD_STOP, BRIDGE_PWRCYCLE, BRIDGE_PWROFF):
            self.spinning = False

    def close(self):
        pass


class FM1828:
    """Background reader thread; delivers Scan objects to a callback."""

    def __init__(self, source, on_scan: Optional[Callable[[Scan], None]] = None):
        self.source = source
        self.parser = StreamParser()
        self.on_scan = on_scan
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.bytes_total = 0
        self.last_scan_time = None
        self.scan_count = 0
        self._lock = threading.Lock()
        self.error = None
        self.error_count = 0

    def open(self):
        self._thread.start()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1.0)
        self.source.close()

    def start_motor(self):
        """Proven start: "$", 2 s, "startlds$" (ran 20+ minutes). "startldspl$" alone only spins the motor for
        about 1-4 s and then the lidar locks like after "stoplds$", so it is not used here."""
        with self._lock:
            self.source.write(CMD_ACK)
            time.sleep(START_DELAY_S)
            self.source.write(CMD_START)
        return True

    def plus_startup(self):
        """Robot's "plus startup" string "startldspl$startlds$" (sent as one write). Use only from a fresh/silent
        state; "startldspl$" without the trailing "startlds$" stops after a few seconds and locks the lidar."""
        with self._lock:
            self.source.write(CMD_START_PLUS + CMD_START)

    def stop_motor(self):
        with self._lock:
            self.source.write(CMD_STOP)

    def send_raw(self, data: bytes):
        with self._lock:
            self.source.write(data)

    def power_cycle(self):
        """Ask the bridge to cut lidar power for 1.5 s (requires the hardware switch on GPIO4)."""
        with self._lock:
            self.source.write(BRIDGE_PWRCYCLE)
        self.parser.last_idx = None

    def restart(self):
        """Power-cycle the lidar, wait for it to boot, then send the start sequence."""
        self.power_cycle()
        time.sleep(1.5 + POWER_SETTLE_S)
        self.start_motor()

    def _run(self):
        import sys, traceback
        while not self._stop.is_set():
            try:
                data = self.source.read()
                if not data:
                    continue
                self.bytes_total += len(data)
                self.parser.feed(data)
                for scan in self.parser.pop_scans():
                    self.scan_count += 1
                    self.last_scan_time = time.monotonic()
                    if self.on_scan:
                        self.on_scan(scan)
            except Exception as e:  # port vanished, parser/callback bug: log and keep the thread alive
                self.error = f'{type(e).__name__}: {e}'
                self.error_count += 1
                traceback.print_exc(file=sys.stderr)
                time.sleep(0.2)

    def status(self) -> dict:
        p = self.parser
        return {
            'bytes': self.bytes_total, 'frames_ok': p.frames_ok, 'frames_bad': p.frames_bad,
            'idle_frames': p.idle_frames, 'junk_bytes': p.junk_bytes, 'ack_seen': p.ack_seen,
            'speed': p.last_speed, 'last_idle_mm': p.last_idle_mm, 'scans': self.scan_count,
            'spinning': bool(self.last_scan_time and time.monotonic() - self.last_scan_time < 1.0),
            'error': self.error or getattr(self.source, 'last_error', None), 'error_count': self.error_count,
            'reconnects': getattr(self.source, 'reconnects', 0),
        }
