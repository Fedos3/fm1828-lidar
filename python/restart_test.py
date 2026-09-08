"""Restart-behaviour test for a freshly power-cycled FM1828 (through the ESP32 bridge).
Sequence: "$" -> startlds$ (8 s) -> "$" (5 s) -> startlds$ (8 s) -> stoplds$ (3 s) -> startlds$ (6 s).
Reports whether each start produced scan frames. Run: python restart_test.py --port /dev/cu.usbserial-10
"""
import argparse, time
from fm1828 import FM1828, SerialSource

p = argparse.ArgumentParser(); p.add_argument('--port', default='/dev/cu.usbserial-10'); a = p.parse_args()
lidar = FM1828(SerialSource(a.port)); lidar.open()
def step(name, data, wait):
    before = lidar.parser.frames_ok
    lidar.send_raw(data); time.sleep(wait)
    got = lidar.parser.frames_ok - before
    print(f"{name:12s} {data!r:14s} wait {wait:>2}s -> scan frames: {got:5d}, idle frames total: {lidar.parser.idle_frames}, ack: {lidar.parser.ack_seen}, speed: {lidar.parser.last_speed}", flush=True)
    return got
step('ack', b'$', 2)
s1 = step('start1', b'startlds$', 8)
step('ack2', b'$', 5)
s2 = step('start2', b'startlds$', 8)
step('stop', b'stoplds$', 3)
s3 = step('start3', b'startlds$', 6)
step('ack3', b'$', 2)
s4 = step('start4', b'startlds$', 6)
print("VERDICT:", "start1", "OK" if s1 else "FAIL", "| restart after $:", "OK" if s2 else "FAIL", "| restart after stoplds$:", "OK" if s3 else "FAIL", "| restart after stoplds$ + $:", "OK" if s4 else "FAIL")
lidar.stop_motor(); time.sleep(1); lidar.close()
