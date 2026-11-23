"""Baixa listas públicas de câmeras de trânsito e gera data/cameras.json.

Formato de saída: [[lat, lon, nome, url_imagem, fonte, url_video_ou_vazio], ...]
Cada fonte é independente: se uma falhar, as outras seguem. O resultado por fonte
vai para data/sources.json, para facilitar o diagnóstico.
Fontes Road511, Iowa e NZTA baseadas no projeto Argus (MIT, github.com/GoSlowPoke168/Argus).
"""
import gzip, json, os, re, sys, time, urllib.parse, urllib.request, concurrent.futures as cf

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 Mirante/1.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Encoding": "gzip",
    "Digitraffic-User": "Mirante/1.0",
}
DATA = os.path.join(os.path.dirname(__file__), "..", "data")
# Hosts de vídeo que não tocam no navegador (exigem login ou não liberam CORS).
BROKEN_STREAM = ("trafficwise.org", "kdot-sfs", "actis.idrivearkansas.com", "api.trafficland.com")


def get(url, timeout=60, params=None, body=None, as_text=False):
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = dict(UA)
    data = None
    if body is not None:
        data = json.dumps(body).encode(); headers["Content-Type"] = "application/json"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                text = raw.decode("utf-8", "replace")
                return text if as_text else json.loads(text)
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


# ---------- OpenCCTV (catálogo global; foco na América Latina) ----------
PROBE = {}
LATAM = (-56.5, -118.5, 33.0, -33.0)   # sul, oeste, norte, leste: México até a Patagônia
OPENCCTV_MAX_BATCHES = 700              # até 35 mil câmeras por rodada, para ser educado com o serviço
OPENCCTV_CACHE = os.path.join(DATA, "cams_opencctv.json")


def _in(box, lat, lon):
    return box[0] <= lat <= box[2] and box[1] <= lon <= box[3]


def _markers():
    """Lê o índice e devolve [(id, lat|None, lon|None)], adaptando-se ao formato."""
    d = get("https://opencctv.org/api/cameras/markers", timeout=120)
    PROBE["opencctv_markers_keys"] = list(d.keys())[:10] if isinstance(d, dict) else type(d).__name__
    items = d.get("markers") or d.get("cameras") or d.get("data") if isinstance(d, dict) else d
    out = []
    if isinstance(d, dict) and isinstance(d.get("ids"), list):
        ids = d["ids"]
        lats = d.get("lats") or d.get("lat") or d.get("latitudes")
        lons = d.get("lngs") or d.get("lng") or d.get("lons") or d.get("longitudes")
        if isinstance(lats, list) and isinstance(lons, list) and len(lats) == len(ids):
            return list(zip(ids, lats, lons))
        PROBE["opencctv_ids_sample"] = ids[:3]
        for i in ids:
            if isinstance(i, (list, tuple)) and len(i) >= 3:
                out.append((i[0], i[1], i[2]))
            elif isinstance(i, dict):
                out.append((i.get("id"), i.get("lat"), i.get("lng") or i.get("lon")))
            else:
                out.append((i, None, None))
        return out
    for i in items or []:
        if isinstance(i, dict):
            out.append((i.get("id"), i.get("lat"), i.get("lng") or i.get("lon")))
        elif isinstance(i, (list, tuple)) and len(i) >= 3:
            out.append((i[0], i[1], i[2]))
    PROBE["opencctv_item_sample"] = (items or [None])[:2]
    return out


def _cctv_record(rec):
    ll = ok(rec.get("lat"), rec.get("lng") or rec.get("lon"))
    url = rec.get("feed_url") or ""
    if not ll or not url or rec.get("proxy_zone") or rec.get("geo_allow"):
        return None
    ft = (rec.get("feed_type") or "image").lower()
    name = rec.get("name") or "Sem nome"
    place = ", ".join(x for x in [rec.get("city"), rec.get("country")] if x)
    label = f"{name}" + (f" · {place}" if place and place.lower() not in name.lower() else "")
    if url.startswith("ipcamlive://"):
        return [*ll, label, "", "OpenCCTV", "iframe:https://www.ipcamlive.com/player/player.php?autoplay=1&alias=" + url[len("ipcamlive://"):]]
    if ft in ("image", "mjpeg"):
        return [*ll, label, url, "OpenCCTV", ""]
    if ft in ("m3u8", "mp4"):
        return [*ll, label, "", "OpenCCTV", url]
    if ft == "iframe" and url.startswith("https://"):
        return [*ll, label, "", "OpenCCTV", "iframe:" + url]
    return None


def opencctv():
    # O catálogo muda pouco: atualiza no máximo uma vez a cada 20 h.
    try:
        cached = json.load(open(OPENCCTV_CACHE, encoding="utf-8"))
        if time.time() - cached.get("ts", 0) < 20 * 3600 and cached.get("cams"):
            return cached["cams"]
    except Exception:
        cached = None
    marks = _markers()
    PROBE["opencctv_total_ids"] = len(marks)
    with_ll = [m for m in marks if m[1] is not None and m[2] is not None]
    if with_ll:
        latam = [m[0] for m in with_ll if _in(LATAM, float(m[1]), float(m[2]))]
        rest = [m[0] for m in with_ll if not _in(LATAM, float(m[1]), float(m[2]))
                and not _in((24, -170, 72, -50), float(m[1]), float(m[2]))]  # EUA/Canadá já têm fontes próprias
        ids = latam + rest
        PROBE["opencctv_latam_ids"] = len(latam)
    else:
        ids = [m[0] for m in marks]
    chunks = [ids[i:i + 50] for i in range(0, len(ids), 50)][:OPENCCTV_MAX_BATCHES]

    def batch(ch):
        try:
            return _batch(ch)
        except Exception as e:
            PROBE["opencctv_batch_error"] = str(e)[:200]
            return []

    def _batch(ch):
        for _ in range(3):
            try:
                return get("https://opencctv.org/api/cameras/batch", body={"ids": ch}, timeout=40)
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    time.sleep(10); continue
                raise
        return []
    out, recs = [], []
    with cf.ThreadPoolExecutor(4) as ex:
        for res in ex.map(batch, chunks):
            recs += res if isinstance(res, list) else (res.get("cameras") or res.get("data") or [])
    if recs:
        PROBE["opencctv_record_keys"] = sorted(recs[0].keys())[:30]
    for r in recs:
        c = _cctv_record(r)
        if c:
            out.append(c)
    json.dump({"ts": time.time(), "cams": out}, open(OPENCCTV_CACHE, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return out


# ---------- ANTT: câmeras das rodovias federais concedidas (dados abertos) ----------
def antt():
    url = "https://dados.antt.gov.br/dataset/a67c5bc2-486f-40b9-99d6-197a0ab3376a/resource/8b371ca4-23b8-46fe-a026-9952b6172db2/download/dados_dos_cftvs.json"
    d = get(url, timeout=90)
    rows = d if isinstance(d, list) else next((v for v in d.values() if isinstance(v, list)), [])
    PROBE["antt_sample"] = rows[:2]
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        low = {k.lower(): v for k, v in r.items()}
        lat = next((v for k, v in low.items() if "lat" in k), None)
        lon = next((v for k, v in low.items() if "lon" in k or "lng" in k), None)
        if isinstance(lat, str): lat = lat.replace(",", ".")
        if isinstance(lon, str): lon = lon.replace(",", ".")
        ll = ok(lat, lon)
        links = [v for v in low.values() if isinstance(v, str) and re.match(r"https?://", v.strip())]
        if not ll or not links:
            continue
        img = next((u for u in links if re.search(r"\.(jpe?g|png)(\?|$)", u, re.I)), "")
        vid = next((u for u in links if re.search(r"\.(m3u8|mp4)(\?|$)", u, re.I)), "")
        page = links[0] if not img and not vid else ""
        name = " ".join(str(low.get(k, "")) for k in ("rodovia", "km", "concessionaria", "local", "descricao") if low.get(k)) or "Sem nome"
        if img or vid or page:
            out.append([*ll, name.strip(), img, "ANTT (rodovias federais)", vid or (("iframe:" + page) if page.startswith("https://") else "")])
    return out


SOURCES = {"tfl": tfl, "digitraffic": digitraffic, "nyc": nyc, "caltrans": caltrans, "drivebc": drivebc,
           "nzta": nzta, "iowa": iowa, "road511": road511, "opencctv": opencctv, "antt": antt}


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
        json.dump({"updated": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "cameras": report, "probe": PROBE}, f, ensure_ascii=False, indent=1, default=str)
    if not cams:
        print("Nenhuma câmera obtida; mantendo arquivo anterior.", file=sys.stderr)
        return
    seen, uniq = set(), []
    for c in cams:
        key = c[3] or c[5]
        if key and key not in seen:
            seen.add(key); uniq.append(c)
    with open(os.path.join(DATA, "cameras.json"), "w", encoding="utf-8") as f:
        json.dump(uniq, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Total: {len(uniq)} câmeras ({sum(1 for c in uniq if c[5])} com vídeo)")


if __name__ == "__main__":
    main()
