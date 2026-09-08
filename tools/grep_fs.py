import re, sys
from PySquashfsImage import SquashFsImage
img = SquashFsImage.from_file(sys.argv[1])
pat = re.compile(rb'startlds|stoplds|lds\$|LDS\$')
hits = []
count = 0
for f in img:
    if not f.is_file: continue
    count += 1
    try: data = f.read_bytes()
    except Exception as e: continue
    if pat.search(data):
        cmds = sorted(set(m.decode('latin-1') for m in re.findall(rb'[\x20-\x7e]{1,40}\$', data)))
        hits.append((f.path, len(data), cmds))
print("files scanned:", count)
for p, n, cmds in hits:
    print(f"HIT {p} ({n} bytes)")
    for c in cmds: print("    ", c)
img.close()
