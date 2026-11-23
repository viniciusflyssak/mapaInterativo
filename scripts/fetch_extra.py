"""Baixa dados que mudam devagar e grava em data/ (evita CORS no navegador).

- data/satellites.json : [[nome, linha1, linha2, grupo], ...]   (CelesTrak)
- data/cables.json     : GeoJSON simplificado dos cabos submarinos (TeleGeography)
- data/airports.json   : [[lat, lon, nome, iata, cidade, país, tipo], ...] (OurAirports)
- data/frontline.json  : GeoJSON das áreas ocupadas na Ucrânia (DeepStateMap)
Cada item é independente: se falhar, o arquivo anterior é mantido.
"""
import csv, io, json, os, sys, urllib.request

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


if __name__ == "__main__":
    for name, fn in [("satélites", satellites), ("cabos", cables), ("aeroportos", airports), ("frente", frontline)]:
        try:
            print(f"{name:11} {fn()}")
        except Exception as e:
            print(f"{name:11} erro: {e}", file=sys.stderr)
