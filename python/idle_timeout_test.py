"""Watch a stopped FM1828 without sending anything; when its idle stream stops by itself, try to start it.
Logs to the file given as argv[1]. Run for up to 50 minutes."""
import serial, sys, time
P = '/dev/cu.usbserial-10'; LOG = sys.argv[1]
def log(m):
    line = time.strftime('%H:%M:%S ') + m
    print(line, flush=True); open(LOG, 'a').write(line + '\n')
def rd(s, secs):
    end = time.monotonic() + secs; buf = b''
    while time.monotonic() < end:
        c = s.read(s.in_waiting or 1)
        if c: buf += c
    return buf
def fa(b): return sum(1 for i in range(len(b) - 61) if b[i] == 0xFA and (sum(b[i:i + 60]) & 0xFFFF) == (b[i + 60] | (b[i + 61] << 8)))
s = serial.Serial(); s.port = P; s.baudrate = 460800; s.timeout = 0.05; s.dtr = False; s.rts = False; s.open()
t0 = time.monotonic(); silent_checks = 0
log("monitor start: no commands are sent until the idle stream stops")
while time.monotonic() - t0 < 50 * 60:
    b = rd(s, 2)
    idle = b.count(b'\x5a\xa5')
    log(f"t+{(time.monotonic()-t0)/60:5.1f} min: {len(b)} bytes, idle frames {idle}, scan {fa(b)}")
    if idle < 50:
        silent_checks += 1
    else:
        silent_checks = 0
    if silent_checks >= 2:
        log("idle stream stopped by itself -> trying startlds$")
        s.write(b'startlds$'); s.flush(); b = rd(s, 6); log(f"  startlds$: {len(b)} bytes, idle {b.count(b'\x5a\xa5')}, scan {fa(b)}, ack {b.count(b'!')}")
        if fa(b) < 50:
            s.write(b'startldspl$'); s.flush(); b = rd(s, 6); log(f"  startldspl$: {len(b)} bytes, idle {b.count(b'\x5a\xa5')}, scan {fa(b)}, ack {b.count(b'!')}")
        if fa(b) >= 50:
            log("STARTED -> stopping again with stoplds$ and continuing to watch for the next timeout")
            s.write(b'stoplds$'); s.flush(); rd(s, 3); silent_checks = 0; t_stop = time.monotonic()
        else:
            log("still not starting; keep watching"); silent_checks = 0
    time.sleep(28)
log("monitor end")
s.close()
