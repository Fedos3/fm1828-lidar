"""Python port of denysvitali/ecovacs-firmware-tools decrypt (AES-128-CBC per section, key derived from type+size)."""
import base64, hashlib, json, os, struct, sys
from Crypto.Cipher import AES

def derive(section_type, size):
    s = f"ZWNvX2Z3X3RhcmdldCAECO-PT1jdSAtpx30byBtYW4{section_type}y5iaW4{size:x}825xxjeff-hk@126.com"
    enc = base64.b64encode(s.encode()).decode()[4:][:len(s)]
    h = hashlib.sha256(enc.encode()).hexdigest()
    return h[35:51].encode(), h[0:16].encode()

def unpad(d):
    if not d: return d
    p = d[-1]
    if 0 < p <= 16 and d[-p:] == bytes([p]) * p: return d[:-p]
    return d

fw = open(sys.argv[1], 'rb').read(); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
sections = []; off = 0; n = len(fw)
while off < n - 72:
    u1, t, u2, size = struct.unpack_from('<BBHI', fw, off)
    if u1 == 1 and t == 1 and 0 < size <= n and off + 8 + size + 64 <= n:
        cs = fw[off + 8 + size: off + 8 + size + 64]
        if all(c in b'0123456789abcdef' for c in cs):
            sections.append((off, u2 >> 12, size, cs.decode())); off += 8 + size + 64
            while off < n and fw[off] == 0: off += 1
            continue
    off += 1
print("sections:", [(o, st, sz) for o, st, sz, _ in sections])
manifest = None
for i, (o, st, sz, cs) in enumerate(sections):
    key, iv = derive(st, sz)
    data = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(fw[o + 8:o + 8 + sz]))
    ok = hashlib.sha256(fw[o:o + 8 + sz]).hexdigest() == cs
    if i == 0:
        manifest = json.loads(data); name = 'manifest.json'; data = json.dumps(manifest, indent=1).encode()
        print("manifest:", {k: manifest.get(k) for k in ('fw_ver', 'hw_ver', 'product', 'release_date')}); print("  sections:", [(s.get('name'), s.get('type'), s.get('size')) for s in manifest['sections']])
    else:
        ms = manifest['sections'][i - 1]; name = ms['name'] + {'sh_script': '.sh', 'fs': '.img', 'img': '.img'}.get(ms['type'], '.bin')
    open(os.path.join(out, name), 'wb').write(data)
    print(f"  wrote {name}: {len(data)} bytes, checksum {'ok' if ok else 'BAD'}, head={data[:8]!r}")
