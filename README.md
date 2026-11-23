# Mirante

Mapa ao vivo com câmeras públicas de trânsito, voos, navios, terremotos, eventos naturais, câmeras mapeadas no OpenStreetMap e usinas.

- `index.html`: o mapa (Leaflet), roda no GitHub Pages.
- `scripts/fetch_cameras.py`: baixa as listas públicas de câmeras (TfL, Digitraffic, NYC DOT, Caltrans, DriveBC, 511 Ontário e Alberta).
- `.github/workflows/cameras.yml`: roda o script a cada 6 h e grava `data/cameras.json`.

Voos (adsb.lol → airplanes.live → OpenSky), navios (Digitraffic), terremotos (USGS), eventos (NASA EONET) e OSM (Overpass) são buscados ao vivo pelo navegador.
