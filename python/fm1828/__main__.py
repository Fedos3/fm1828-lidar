"""CLI: python -m fm1828 --port /dev/cu.usbserial-10 [--seconds 10] | --replay file.bin ; prints per-scan stats."""
import argparse, time
from . import FM1828, SerialSource, ReplaySource

p = argparse.ArgumentParser()
p.add_argument('--port', default=None)
p.add_argument('--replay', default=None)
p.add_argument('--seconds', type=float, default=10)
p.add_argument('--no-start', action='store_true', help='do not send start command (lidar already spinning)')
p.add_argument('--stop', action='store_true', help='send stoplds$ at the end')
a = p.parse_args()
src = ReplaySource(a.replay) if a.replay else SerialSource(a.port)
def on_scan(s):
    print(f"scan {lidar.scan_count}: {len(s.points)} pts, frames={s.frames}, missing={s.missing_frames}, speed={s.speed}")
lidar = FM1828(src, on_scan)
lidar.open()
if not a.no_start:
    lidar.start_motor()
t = time.time() + a.seconds
while time.time() < t:
    time.sleep(0.5)
print(lidar.status())
if a.stop:
    lidar.stop_motor(); time.sleep(1)
lidar.close()
