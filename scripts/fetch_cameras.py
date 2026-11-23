"""Baixa listas públicas de câmeras de trânsito e gera data/cameras.json.

Formato de saída (compacto): [[lat, lon, nome, url_imagem, fonte, url_video_ou_vazio], ...]
Cada fonte é independente: se uma falhar, as outras seguem.
"""
import json, os, sys, urllib.request, concurrent.futures as cf

UA = {"User-Agent": "Mirante/1.0 (github pages map)", "Digitraffic-User": "Mirante/1.0", "Accept": "application/json"}
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "cameras.json")


def get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def ok(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0):
        return round(lat, 5), round(lon, 5)
    return None


def tfl():
    out = []
    for c in get("https://api.tfl.gov.uk/Place/Type/JamCam"):
        p = {a.get("key"): a.get("value") for a in c.get("additionalProperties", [])}
        ll = ok(c.get("lat"), c.get("lon"))
        if ll and p.get("imageUrl"):
            out.append([*ll, c.get("commonName", "JamCam"), p["imageUrl"], "TfL Londres", p.get("videoUrl", "")])
    return out


def digitraffic():
    out = []
    for f in get("https://tie.digitraffic.fi/api/weathercam/v1/stations").get("features", []):
        lon, lat = f["geometry"]["coordinates"][:2]
        pr = f.get("properties", {})
        presets = pr.get("presets") or []
        ll = ok(lat, lon)
        if ll and presets:
            pid = presets[0].get("id")
            out.append([*ll, pr.get("name", pid), f"https://weathercam.digitraffic.fi/{pid}.jpg", "Digitraffic Finlândia", ""])
    return out


def nyc():
    out = []
    for c in get("https://webcams.nyctmc.org/api/cameras"):
        ll = ok(c.get("latitude"), c.get("longitude"))
        if ll and c.get("imageUrl") and str(c.get("isOnline", "true")).lower() != "false":
            out.append([*ll, c.get("name", "NYC DOT"), c["imageUrl"], "NYC DOT", ""])
    return out


def caltrans_district(d):
    out = []
    data = get(f"https://cwwp2.dot.ca.gov/data/d{d}/cctv/cctvStatusD{d:02d}.json").get("data", [])
    for item in data:
        c = item.get("cctv", {})
        if str(c.get("inService", "true")).lower() != "true":
            continue
        loc = c.get("location", {})
        img = c.get("imageData", {})
        ll = ok(loc.get("latitude"), loc.get("longitude"))
        url = (img.get("static") or {}).get("currentImageURL")
        if ll and url and url.startswith("http"):
            out.append([*ll, loc.get("locationName", "Caltrans"), url, "Caltrans", img.get("streamingVideoURL", "") or ""])
    return out


def caltrans():
    out = []
    for d in range(1, 13):
        try:
            out += caltrans_district(d)
        except Exception as e:  # um distrito fora do ar não derruba os outros
            print(f"  caltrans d{d}: {e}", file=sys.stderr)
    return out


def drivebc():
    out = []
    data = get("https://images.drivebc.ca/webcam/api/v1/webcams")
    for c in data.get("webcams", data if isinstance(data, list) else []):
        loc = c.get("location", {})
        ll = ok(loc.get("latitude"), loc.get("longitude"))
        img = (c.get("links") or {}).get("imageDisplay")
        if ll and img:
            out.append([*ll, c.get("camName", "DriveBC"), img, "DriveBC Canadá", ""])
    return out


def iteris(url, label):
    """Plataforma 511 usada por Ontário, Alberta e outros (sem chave)."""
    out = []
    for c in get(url):
        ll = ok(c.get("Latitude"), c.get("Longitude"))
        views = c.get("Views") or []
        img = (views[0].get("Url") if views else None) or c.get("Url")
        if ll and img:
            out.append([*ll, c.get("Location") or c.get("Name") or label, img, label, ""])
    return out


SOURCES = {
    "tfl": tfl,
    "digitraffic": digitraffic,
    "nyc": nyc,
    "caltrans": caltrans,
    "drivebc": drivebc,
    "ontario": lambda: iteris("https://511on.ca/api/v2/get/cameras", "511 Ontário"),
    "alberta": lambda: iteris("https://511.alberta.ca/api/v2/get/cameras", "511 Alberta"),
}


def main():
    cams, report = [], {}
    with cf.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(fn): name for name, fn in SOURCES.items()}
        for fut in cf.as_completed(futs):
            name = futs[fut]
            try:
                got = fut.result()
                cams += got
                report[name] = len(got)
            except Exception as e:
                report[name] = f"erro: {e}"
    for k, v in sorted(report.items()):
        print(f"{k:12} {v}")
    if not cams:
        print("Nenhuma câmera obtida; mantendo arquivo anterior.", file=sys.stderr)
        return
    seen, uniq = set(), []
    for c in cams:
        if c[3] not in seen:
            seen.add(c[3]); uniq.append(c)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Total: {len(uniq)} câmeras")


if __name__ == "__main__":
    main()
