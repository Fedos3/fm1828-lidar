"""Query the Ecovacs OTA API (same endpoint as denysvitali/ecovacs-firmware-tools) for available firmware."""
import json, sys, urllib.request, urllib.error, itertools
UA = "Dalvik/2.1.0 (Linux; U; Android 5.1.1; A5010 Build/LMY48Z)"
servers = ["portal-ww.ecouser.net", "portal-eu.ecouser.net", "portal-us.ecouser.net", "portal-cn.ecouser.net"]
models = sys.argv[1].split(',')
modules = (sys.argv[2] if len(sys.argv) > 2 else "fw0,mcu").split(',')
versions = ["1.0.0", "1.4.8", "1.2.9", "1.5.0", "1.17.0", "1.22.0", "1.55.0", "0.0.1", "1.1.0", "1.3.0", "1.6.0", "1.8.0", "1.10.0", "1.12.0", "1.20.0", "1.30.0", "1.40.0", "1.60.0", "1.70.0", "1.80.0", "1.90.0", "2.0.0"]
found = {}
for model, module in itertools.product(models, modules):
    for server in servers:
        hit = None
        for ver in versions:
            url = f"https://{server}/api/ota/products/wukong/class/{model}/firmware/latest.json?ver={ver}&module={module}"
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                body = urllib.request.urlopen(req, timeout=15).read()
            except urllib.error.HTTPError as e:
                print(f"{model} {module} {server} ver={ver}: HTTP {e.code}", file=sys.stderr); continue
            except Exception as e:
                print(f"{model} {module} {server} ver={ver}: {e}", file=sys.stderr); break
            if body.strip() == b"Not Found" or not body.strip():
                continue
            try:
                data = json.loads(body)
            except Exception:
                print(f"{model} {module} {server} ver={ver}: non-JSON {body[:80]!r}", file=sys.stderr); continue
            md = data.get(module) or {}
            if md.get("url"):
                key = (model, module, md.get("version"))
                if key not in found:
                    found[key] = {"server": server, "probe_ver": ver, "name": data.get("name"), "version": md.get("version"), "size": md.get("size"), "checkSum": md.get("checkSum"), "url": md.get("url")}
                    print("FOUND", json.dumps(found[key]), flush=True)
                hit = True
            else:
                print(f"{model} {module} {server} ver={ver}: keys={list(data.keys())}", file=sys.stderr)
        if hit:
            break
json.dump(list(found.values()), open("found.json", "w"), indent=1)
print("total found:", len(found))
