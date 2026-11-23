"""Coleta posições de navios no mundo todo pela AISStream (chave gratuita em aisstream.io).

Escuta o fluxo AIS por COLLECT_SECONDS e grava ships.json:
{"updated": epoch, "ships": [[mmsi, lat, lon, sog, cog, heading, nome, tipo, epoch_posicao], ...]}
Sem a variável AISSTREAM_KEY, sai sem fazer nada.
"""
import asyncio, json, os, sys, time

COLLECT_SECONDS = int(os.environ.get("COLLECT_SECONDS", "150"))
OUT = sys.argv[1] if len(sys.argv) > 1 else "ships.json"


async def main(key):
    import websockets
    ships, names = {}, {}
    sub = {"APIKey": key, "BoundingBoxes": [[[-90, -180], [90, 180]]],
           "FilterMessageTypes": ["PositionReport", "StandardClassBPositionReport", "ShipStaticData"]}
    end = time.time() + COLLECT_SECONDS
    async with websockets.connect("wss://stream.aisstream.io/v0/stream", max_size=2**22) as ws:
        await ws.send(json.dumps(sub))
        while time.time() < end:
            try:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
            except asyncio.TimeoutError:
                continue
            if "error" in msg:
                raise RuntimeError(msg["error"])
            meta, kind = msg.get("MetaData", {}), msg.get("MessageType")
            body = (msg.get("Message") or {}).get(kind) or {}
            mmsi = meta.get("MMSI") or body.get("UserID")
            if not mmsi:
                continue
            if kind == "ShipStaticData":
                names[mmsi] = ((body.get("Name") or "").strip(), body.get("Type"))
                continue
            lat, lon = body.get("Latitude"), body.get("Longitude")
            if lat is None or lon is None or abs(lat) > 90 or abs(lon) > 180:
                continue
            ships[mmsi] = [mmsi, round(lat, 4), round(lon, 4), body.get("Sog"), body.get("Cog"), body.get("TrueHeading"),
                           (meta.get("ShipName") or "").strip(), None, int(time.time())]
    for m, s in ships.items():
        if m in names:
            s[6] = s[6] or names[m][0]
            s[7] = names[m][1]
    return list(ships.values())


if __name__ == "__main__":
    key = os.environ.get("AISSTREAM_KEY", "").strip()
    if not key:
        print("AISSTREAM_KEY não configurada; nada a fazer.")
        sys.exit(0)
    data = asyncio.run(main(key))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"updated": int(time.time()), "ships": data}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(data)} navios")
