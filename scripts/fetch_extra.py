"""Baixa dados que mudam devagar e grava em data/ (evita CORS no navegador).

- data/satellites.json : [[nome, linha1, linha2, grupo, id_intl, país, data_lanç, local, tipo, rcs], ...] (CelesTrak TLE + SATCAT)
- data/cables.json     : GeoJSON simplificado dos cabos submarinos (TeleGeography)
- data/airports.json   : [[lat, lon, nome, iata, cidade, país, tipo], ...] (OurAirports)
- data/frontline.json  : GeoJSON das áreas ocupadas na Ucrânia (DeepStateMap)
Cada item é independente: se falhar, o arquivo anterior é mantido.
"""
import csv, io, json, os, sys, time, urllib.parse, urllib.request

UA = {"User-Agent": "Mirante/1.0 (github.com/viniciusflyssak/mapaInterativo)"}
DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def get(url, timeout=90):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def save(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def rnd(coords, n=3):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], n), round(coords[1], n)]
    return [rnd(c, n) for c in coords]


def satellites():
    out, seen = [], set()
    for group in ["stations", "visual", "gps-ops", "weather", "science", "geo", "starlink"]:
        lines = [l.rstrip() for l in get(f"https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle").splitlines() if l.strip()]
        for i in range(0, len(lines) - 2, 3):
            name, l1, l2 = lines[i].strip(), lines[i + 1], lines[i + 2]
            if not (l1.startswith("1 ") and l2.startswith("2 ")):
                continue
            norad = l1[2:7]
            if norad in seen:
                continue
            seen.add(norad)
            out.append([name, l1, l2, group])
    # Metadados do catálogo (país, lançamento, local, tipo). Se falhar, segue só com o TLE.
    try:
        cat = {r["NORAD_CAT_ID"].zfill(5): r for r in csv.DictReader(io.StringIO(get("https://celestrak.org/pub/satcat.csv", 180)))}
        for sat in out:
            r = cat.get(sat[1][2:7].strip().zfill(5))
            if r:
                sat += [r.get("OBJECT_ID", ""), r.get("OWNER", ""), r.get("LAUNCH_DATE", ""), r.get("LAUNCH_SITE", ""), r.get("OBJECT_TYPE", ""), r.get("RCS", "")]
    except Exception as e:
        print(f"  satcat: {e}", file=sys.stderr)
    save("satellites.json", out)
    return len(out)


def cables():
    geo = json.loads(get("https://www.submarinecablemap.com/api/v3/cable/cable-geo.json"))
    feats = [{"type": "Feature", "properties": {"n": f["properties"].get("name", ""), "c": f["properties"].get("color", "#4cc9f0")},
              "geometry": {"type": f["geometry"]["type"], "coordinates": rnd(f["geometry"]["coordinates"], 2)}}
             for f in geo.get("features", []) if f.get("geometry")]
    save("cables.json", {"type": "FeatureCollection", "features": feats})
    return len(feats)


def airports():
    rows = csv.DictReader(io.StringIO(get("https://davidmegginson.github.io/ourairports-data/airports.csv")))
    out = []
    for r in rows:
        if r["type"] not in ("large_airport", "medium_airport") or r["scheduled_service"] != "yes":
            continue
        out.append([round(float(r["latitude_deg"]), 4), round(float(r["longitude_deg"]), 4), r["name"], r["iata_code"],
                    r["municipality"], r["iso_country"], "G" if r["type"] == "large_airport" else "M"])
    save("airports.json", out)
    return len(out)


def frontline():
    d = json.loads(get("https://deepstatemap.live/api/history/last"))
    src = d.get("map", d)
    feats = []
    for f in src.get("features", []):
        g = f.get("geometry") or {}
        if g.get("type") in ("Polygon", "MultiPolygon"):
            feats.append({"type": "Feature", "properties": {"n": (f.get("properties") or {}).get("name", "")},
                          "geometry": {"type": g["type"], "coordinates": rnd(g["coordinates"], 3)}})
    if not feats:
        raise ValueError("sem polígonos")
    save("frontline.json", {"type": "FeatureCollection", "updated": d.get("datetime") or d.get("createdAt"), "features": feats})
    return len(feats)


def powerplants():
    """WRI Global Power Plant Database (CC BY 4.0), ~35 mil usinas; última versão publicada em 2021."""
    rows = csv.DictReader(io.StringIO(get("https://raw.githubusercontent.com/wri/global-power-plant-database/master/output_database/global_power_plant_database.csv", 180)))
    out = []
    for r in rows:
        try:
            lat, lon = round(float(r["latitude"]), 4), round(float(r["longitude"]), 4)
        except (ValueError, KeyError):
            continue
        cap = r.get("capacity_mw") or ""
        out.append([lat, lon, r.get("name", ""), r.get("primary_fuel", ""), round(float(cap), 1) if cap else None,
                    r.get("owner", ""), r.get("commissioning_year", "")[:4], r.get("country_long", "")])
    save("powerplants.json", out)
    return len(out)


OSM_COUNTRIES = ["BR", "AR", "CL", "UY", "PY", "BO", "PE", "EC", "CO", "VE", "GY", "SR", "GF", "MX"]
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]


def overpass(query):
    last = None
    for url in OVERPASS:
        try:
            data = urllib.parse.urlencode({"data": query}).encode()
            req = urllib.request.Request(url, data=data, headers=UA)
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(10)
    raise last


def osm_latam():
    """Câmeras de vigilância mapeadas no OpenStreetMap (ODbL) na América Latina: [lat, lon, tipo, operador, país]."""
    out, report = [], {}
    for cc in OSM_COUNTRIES:
        try:
            d = overpass(f'[out:json][timeout:240];area["ISO3166-1"="{cc}"][admin_level=2]->.a;node["man_made"="surveillance"](area.a);out;')
            n = 0
            for el in d.get("elements", []):
                t = el.get("tags", {})
                out.append([round(el["lat"], 5), round(el["lon"], 5), t.get("surveillance:type") or t.get("surveillance") or "",
                            t.get("operator") or "", cc])
                n += 1
            report[cc] = n
        except Exception as e:
            report[cc] = f"erro: {str(e)[:100]}"
        time.sleep(5)  # uma consulta por vez, com pausa: uso educado do Overpass
    if out:
        save("osm_latam.json", out)
    print("  osm por país:", report)
    return len(out)


def antt_cftv():
    """Câmeras (CFTV) das rodovias federais concedidas, dados abertos da ANTT. Só localização, sem imagem.
    Saída: [lat, lon, rodovia, km, município, uf, concessionária, sentido]"""
    pkg = json.loads(get("https://dados.antt.gov.br/api/3/action/package_show?id=cftv", 180))["result"]
    res = [r for r in pkg.get("resources", []) if r.get("url", "").endswith(".json")]
    res.sort(key=lambda r: r.get("last_modified") or r.get("created") or "", reverse=True)
    last = None
    for r in res:
        try:
            rows = json.loads(get(r["url"], 300))
            break
        except Exception as e:
            last = e
    else:
        raise last or RuntimeError("sem recurso JSON")
    if isinstance(rows, dict):
        rows = next((v for v in rows.values() if isinstance(v, list)), [])
    out = []
    num = lambda v: float(str(v).replace(",", ".")) if v not in (None, "") else None
    for r in rows:
        if (r.get("situacao") or "").strip().lower() not in ("ativo", "ativa"):
            continue
        try:
            lat, lon = num(r.get("latitude")), num(r.get("longitude"))
        except ValueError:
            continue
        if lat is None or lon is None or not (-35 < lat < 6 and -75 < lon < -30):
            continue
        out.append([round(lat, 5), round(lon, 5), r.get("rodovia") or "", r.get("km_m") or "", r.get("municipio") or "",
                    r.get("uf") or "", r.get("concessionaria") or "", r.get("sentido") or ""])
    save("cftv_antt.json", out)
    return len(out)


if __name__ == "__main__":
    for name, fn in [("satélites", satellites), ("cabos", cables), ("aeroportos", airports), ("frente", frontline), ("usinas", powerplants), ("vigilância OSM", osm_latam), ("CFTV ANTT", antt_cftv)]:
        try:
            print(f"{name:11} {fn()}")
        except Exception as e:
            print(f"{name:11} erro: {e}", file=sys.stderr)
