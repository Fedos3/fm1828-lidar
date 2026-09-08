"""Reset ESP32, then send manual lidar commands one by one and print each RESULT line.
Each argument is sent verbatim to the lidar (use \\r \\n escapes); the firmware listens 3 s after each."""
import argparse, time, serial
p = argparse.ArgumentParser()
p.add_argument('--port', default='/dev/cu.usbserial-110')
p.add_argument('--baud', type=int, default=460800)
p.add_argument('--log', default=None)
p.add_argument('--gap', type=float, default=0.5, help='seconds between commands after RESULT')
p.add_argument('commands', nargs='+')
a = p.parse_args()
log = open(a.log, 'ab') if a.log else None
def rd(port, until, timeout):
    buf = b''; end = time.monotonic() + timeout
    while time.monotonic() < end:
        c = port.read(port.in_waiting or 1)
        if c:
            buf += c
            if log: log.write(c); log.flush()
            if until in buf: break
    return buf
with serial.Serial(a.port, a.baud, timeout=0.2) as port:
    port.dtr = False; port.rts = True; time.sleep(0.15); port.rts = False
    rd(port, b'READY:', 6)
    for cmd in a.commands:
        if cmd.startswith(':b'):
            port.write((cmd + '\n').encode()); out = rd(port, b'MANUAL baud', 3)
        else:
            port.write((':' + cmd + '\n').encode()); out = rd(port, b'ASCII=', 8); rd(port, b'\n', 1)
        for line in out.decode('utf-8', 'replace').splitlines():
            if line.startswith(('RESULT', 'MANUAL', 'BEGIN')):
                if line.startswith('RESULT'):
                    hexpart = line.split('HEX=')[1].split(' ASCII=')[0].strip()
                    fa = hexpart.count('FA '); print(f"CMD {cmd!r}: {line.split(' HEX=')[0]} FA_in_sample={fa} sample={hexpart[:60]}")
        time.sleep(a.gap)
