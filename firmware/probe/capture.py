"""Reset ESP32, wait for READY, send one command character, save the full USB console output (may contain raw binary)."""
import argparse
import pathlib
import time
import serial

parser = argparse.ArgumentParser()
parser.add_argument('--port', default='/dev/cu.usbserial-110')
parser.add_argument('--baud', type=int, default=460800)
parser.add_argument('--command', default='g')
parser.add_argument('--seconds', type=float, default=120)
parser.add_argument('--output', default='captures/ecovacs-probe.txt')
parser.add_argument('--quiet', action='store_true', help='do not echo output to stdout (use for raw dumps)')
parser.add_argument('--no-reset', action='store_true', help='do not reset the ESP32; send the command immediately (firmware must already be at READY)')
args = parser.parse_args()
out = pathlib.Path(args.output)
out.parent.mkdir(parents=True, exist_ok=True)
port = serial.Serial()
port.port, port.baudrate, port.timeout = args.port, args.baud, 0.5
port.dtr = False
port.rts = False
port.open()
with port, out.open('wb') as f:
    if not args.no_reset:
        port.rts = True
        time.sleep(0.15)
        port.rts = False
    end = time.monotonic() + args.seconds
    ready_buffer = b''
    sent = False
    total = 0
    if args.no_reset:
        port.write(args.command.encode())
        sent = True
    while time.monotonic() < end:
        chunk = port.read(port.in_waiting or 1)
        if chunk:
            total += len(chunk)
            ready_buffer = (ready_buffer + chunk)[-4096:]
            if not sent and b'READY:' in ready_buffer:
                port.write(args.command.encode())
                sent = True
            f.write(chunk)
            f.flush()
            if not args.quiet:
                print(chunk.decode('utf-8', errors='replace'), end='', flush=True)
            if b'DONE ' + args.command.encode() in ready_buffer or b'PROBE COMPLETE' in ready_buffer:
                break
    print(f'\n[capture] {total} bytes saved to {out}', flush=True)
