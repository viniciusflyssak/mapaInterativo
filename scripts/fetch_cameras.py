"""Baixa listas públicas de câmeras de trânsito e gera data/cameras.json.

Formato de saída: [[lat, lon, nome, url_imagem, fonte, url_video_ou_vazio], ...]
Cada fonte é independente: se uma falhar, as outras seguem. O resultado por fonte
vai para data/sources.json, para facilitar o diagnóstico.
Fontes Road511, Iowa e NZTA baseadas no projeto Argus (MIT, github.com/GoSlowPoke168/Argus).
"""
import gzip, json, os, sys, time, urllib.parse, urllib.request, concurrent.futures as cf

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 Mirante/1.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip",
    "Digitraffic-User": "Mirante/1.0",
}
DATA = os.path.join(os.path.dirname(__file__), "..", "data")
# Hosts de vídeo que não tocam no navegador (exigem login ou não liberam CORS).
BROKEN_STREAM = ("trafficwise.org", "kdot-sfs", "actis.idrivearkansas.com", "api.trafficland.com")


def get(url, timeout=60, params=None):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(5); continue
            raise


def ok(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return None
    if -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0):
        return round(lat, 5), round(lon, 5)
    return None


def video(url):
    return "" if not url or any(h in url for h in BROKEN_STREAM) else url


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
        presets = [p for p in (pr.get("presets") or []) if p.get("inCollection", True)]
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


def caltrans():
    out = []
    for d in range(1, 13):
        try:
            for item in get(f"https://cwwp2.dot.ca.gov/data/d{d}/cctv/cctvStatusD{d:02d}.json").get("data", []):
                c = item.get("cctv", {})
                if str(c.get("inService", "true")).lower() != "true":
                    continue
                loc, img = c.get("location", {}), c.get("imageData", {})
                ll = ok(loc.get("latitude"), loc.get("longitude"))
                url = (img.get("static") or {}).get("currentImageURL")
                if ll and url and url.startswith("http"):
                    out.append([*ll, loc.get("locationName", "Caltrans"), url, "Caltrans", video(img.get("streamingVideoURL", ""))])
        except Exception as e:
            print(f"  caltrans d{d}: {e}", file=sys.stderr)
    return out


def drivebc():
    out = []
    data = get("https://www.drivebc.ca/api/webcams/", params={"format": "json"})
    for c in (data.get("webcams", []) if isinstance(data, dict) else data):
        if c.get("is_on") is False:
            continue
        coords = (c.get("location") or {}).get("coordinates") or []
        ll = ok(coords[1], coords[0]) if len(coords) >= 2 else None
        img = (c.get("links") or {}).get("imageDisplay", "")
        if ll and img:
            out.append([*ll, c.get("name", "DriveBC"), img if img.startswith("http") else "https://www.drivebc.ca" + img, "DriveBC Canadá", ""])
    return out


def nzta():
    out = []
    for c in get("https://trafficnz.info/service/traffic/rest/4/cameras/all").get("response", {}).get("camera", []):
        if c.get("offline") or c.get("underMaintenance"):
            continue
        ll = ok(c.get("latitude"), c.get("longitude"))
        img = c.get("imageUrl") or ""
        if ll and img:
            out.append([*ll, c.get("name", "NZTA"), img if img.startswith("http") else "https://trafficnz.info" + img, "NZTA Nova Zelândia", ""])
    return out


def iowa():
    out, offset = [], 0
    base = "https://services.arcgis.com/8lRhdTsQyJpO52F1/ArcGIS/rest/services/Traffic_Cameras_View/FeatureServer/0/query"
    while True:
        d = get(base, params={"where": "1=1", "outFields": "*", "f": "json", "resultOffset": offset, "resultRecordCount": 1000})
        feats = d.get("features", [])
        for f in feats:
            a = f.get("attributes", {})
            ll = ok(a.get("latitude") or a.get("lat"), a.get("longitude") or a.get("long"))
            img = a.get("ImageURL") or ""
            if ll and img:
                out.append([*ll, a.get("Desc_") or a.get("ImageName") or "Iowa DOT", img, "Iowa DOT", video(a.get("VideoURL") or a.get("VideoUR") or "")])
        if not feats or not d.get("exceededTransferLimit"):
            break
        offset += len(feats)
    return out


ROAD511_STATES = ["FL", "UT", "WA", "OR", "CO", "SC", "IN", "TN", "AZ", "KS", "AR", "OH", "KY", "NE", "DE", "MA", "WY", "ND", "SD", "MT"]


def road511_state(st):
    out, offset = [], 0
    while True:
        d = get("https://api.road511.com/api/v1/features", params={"type": "cameras", "jurisdiction": st, "limit": 500, "offset": offset})
        cams = d.get("data") or []
        for c in cams:
            if not c.get("is_active", True):
                continue
            ll = ok(c.get("latitude"), c.get("longitude"))
            p = c.get("properties") or {}
            img, vid = p.get("image_url") or "", video(p.get("video_url") or "")
            if ll and img:
                out.append([*ll, c.get("name") or f"{st} DOT", img, f"Road511 {st}", vid])
        if not cams or not d.get("has_more"):
            break
        offset += len(cams)
        time.sleep(0.3)
    return out


def road511():
    out = []
    for st in ROAD511_STATES:
        try:
            out += road511_state(st)
        except Exception as e:
            print(f"  road511 {st}: {e}", file=sys.stderr)
    return out


SOURCES = {"tfl": tfl, "digitraffic": digitraffic, "nyc": nyc, "caltrans": caltrans, "drivebc": drivebc,
           "nzta": nzta, "iowa": iowa, "road511": road511}


def main():
    cams, report = [], {}
    with cf.ThreadPoolExecutor(8) as ex:
        futs = {ex.submit(fn): name for name, fn in SOURCES.items()}
        for fut in cf.as_completed(futs):
            name = futs[fut]
            try:
                got = fut.result(); cams += got; report[name] = len(got)
            except Exception as e:
                report[name] = f"erro: {str(e)[:200]}"
    for k, v in sorted(report.items()):
        print(f"{k:12} {v}")
    with open(os.path.join(DATA, "sources.json"), "w", encoding="utf-8") as f:
        json.dump({"updated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "cameras": report}, f, ensure_ascii=False, indent=1)
    if not cams:
        print("Nenhuma câmera obtida; mantendo arquivo anterior.", file=sys.stderr)
        return
    seen, uniq = set(), []
    for c in cams:
        if c[3] not in seen:
            seen.add(c[3]); uniq.append(c)
    with open(os.path.join(DATA, "cameras.json"), "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Total: {len(uniq)} câmeras ({sum(1 for c in uniq if c[5])} com vídeo)")


if __name__ == "__main__":
    main()
