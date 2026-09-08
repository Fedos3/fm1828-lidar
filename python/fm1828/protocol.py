"""FM1828 wire protocol (verified 2026-09-08 on real hardware).

UART 460800 8N1, 3.3 V. Commands (ASCII): "$" -> 0x21 once after power-on, then idle frames;
"startlds$" -> motor spins, scan frames; "stoplds$" -> motor stops, back to idle frames.

Idle frame (4 bytes): 5A A5 <dist_hi> <dist_lo>   distance in mm, big-endian, ~1000/s.
Scan frame (62 bytes, little-endian):
  [0]     0xFA
  [1]     frame index 0xA0..0xF9 (90 frames per revolution, 4 degrees each)
  [2:4]   speed, uint16 (about 30100 when spinning steadily at ~5 rev/s; units unknown)
  [4:36]  16 x uint16 distance in mm (0.25 degree step); 0 or >= 32000 means no return
  [36:60] 24 bytes: 00 02 <counter uint16> then zeros; counter wraps at 65536
  [60:62] checksum uint16 = arithmetic sum of bytes 0..59
"""
from dataclasses import dataclass, field
from typing import List, Optional

FRAME_LEN = 62
IDX_FIRST = 0xA0
IDX_LAST = 0xF9
FRAMES_PER_REV = IDX_LAST - IDX_FIRST + 1  # 90
POINTS_PER_FRAME = 16
DEG_PER_FRAME = 360.0 / FRAMES_PER_REV       # 4.0
DEG_PER_POINT = DEG_PER_FRAME / POINTS_PER_FRAME  # 0.25
MAX_VALID_MM = 32000


def angle_of(idx: int, point: int) -> float:
    """Angle in degrees for frame index (0xA0..0xF9) and point number (0..15)."""
    return (idx - IDX_FIRST) * DEG_PER_FRAME + point * DEG_PER_POINT


@dataclass
class IdleFrame:
    distance_mm: int


@dataclass
class Frame:
    idx: int
    speed: int
    distances: List[int]
    counter: int
    raw: bytes = field(repr=False)

    @property
    def number(self) -> int:
        return self.idx - IDX_FIRST

    def points(self):
        """Yield (angle_deg, distance_mm, valid) for the 16 points."""
        for j, d in enumerate(self.distances):
            yield angle_of(self.idx, j), d, 0 < d < MAX_VALID_MM


@dataclass
class Scan:
    """One revolution: list of (angle_deg, distance_mm) valid points plus stats."""
    points: List[tuple]
    frames: int
    speed: int
    missing_frames: int


def parse_frame(buf: bytes) -> Optional[Frame]:
    if len(buf) < FRAME_LEN or buf[0] != 0xFA:
        return None
    if (sum(buf[:60]) & 0xFFFF) != (buf[60] | (buf[61] << 8)):
        return None
    idx = buf[1]
    if not (IDX_FIRST <= idx <= IDX_LAST):
        return None
    d = [buf[4 + 2 * k] | (buf[5 + 2 * k] << 8) for k in range(POINTS_PER_FRAME)]
    return Frame(idx=idx, speed=buf[2] | (buf[3] << 8), distances=d, counter=buf[38] | (buf[39] << 8), raw=bytes(buf[:FRAME_LEN]))


class StreamParser:
    """Incremental parser: feed() bytes, get frames/idle frames; assembles scans per revolution."""

    def __init__(self):
        self._buf = bytearray()
        self.frames_ok = 0
        self.frames_bad = 0
        self.idle_frames = 0
        self.junk_bytes = 0
        self.ack_seen = 0
        self.last_idle_mm = None
        self.last_speed = 0
        self.last_idx = None
        self._scan_points = []
        self._scan_frames = 0
        self._scan_missing = 0
        self.scans = []

    def feed(self, data: bytes):
        """Feed raw bytes. Returns list of Frame objects parsed from this call."""
        self._buf += data
        out = []
        b = self._buf
        i = 0
        n = len(b)
        while i < n:
            c = b[i]
            if c == 0xFA:
                if n - i < FRAME_LEN:
                    break  # wait for more data
                fr = parse_frame(b[i:i + FRAME_LEN])
                if fr:
                    self.frames_ok += 1
                    self._on_frame(fr)
                    out.append(fr)
                    i += FRAME_LEN
                    continue
                self.frames_bad += 1
                i += 1
                continue
            if c == 0x5A:
                if n - i < 4:
                    break
                if b[i + 1] == 0xA5:
                    self.idle_frames += 1
                    self.last_idle_mm = (b[i + 2] << 8) | b[i + 3]
                    i += 4
                    continue
                self.junk_bytes += 1
                i += 1
                continue
            if c == 0x21:
                self.ack_seen += 1
            else:
                self.junk_bytes += 1
            i += 1
        del b[:i]
        if len(b) > 4096:  # runaway junk protection
            del b[:-256]
        return out

    def _on_frame(self, fr: Frame):
        self.last_speed = fr.speed
        if self.last_idx is not None:
            if fr.idx < self.last_idx:  # wrapped: revolution complete
                self.scans.append(Scan(points=self._scan_points, frames=self._scan_frames,
                                       speed=fr.speed, missing_frames=self._scan_missing))
                self._scan_points, self._scan_frames, self._scan_missing = [], 0, 0
            else:
                gap = fr.idx - self.last_idx - 1
                if gap > 0:
                    self._scan_missing += gap
        self.last_idx = fr.idx
        self._scan_frames += 1
        for ang, d, ok in fr.points():
            if ok:
                self._scan_points.append((ang, d))

    def pop_scans(self):
        s, self.scans = self.scans, []
        return s
