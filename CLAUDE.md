# Mirante (mapaInterativo): contexto do projeto

Resumo para continuar o trabalho num chat novo. Mantenha este arquivo atualizado a cada mudança relevante.

## O que é
Mapa interativo ao vivo inspirado no **Argos Atlas** (argosatlas.com), feito só com fontes gratuitas e públicas.
- Repositório: github.com/viniciusflyssak/mapaInterativo (público)
- Site: https://viniciusflyssak.github.io/mapaInterativo/ (GitHub Pages, branch `main`, raiz)
- Dono usa principalmente o **celular** (Chrome Android); testar layout mobile primeiro.

## Estrutura
| Arquivo | Função |
|---|---|
| `index.html` | App inteiro (HTML+CSS+JS, Leaflet 1.9.4 + MarkerCluster 1.5.3 via unpkg) |
| `scripts/fetch_cameras.py` | Baixa listas de câmeras no servidor (evita CORS) e grava `data/cameras.json` |
| `scripts/fetch_extra.py` | Satélites (CelesTrak TLE), cabos (TeleGeography), aeroportos (OurAirports), frente na Ucrânia (DeepStateMap) → `data/*.json` |
| `.github/workflows/cameras.yml` | "Atualizar dados": roda os dois scripts a cada 6 h, manualmente ou em push nos scripts; faz commit de `data/` |
| `data/cameras.json` | `[[lat, lon, nome, url_imagem, fonte, url_video], ...]`, gerado pela Action |
| `api/flights.js` | Função serverless da Vercel (proxy CORS de voos). O mapa detecta `/api/flights` no mesmo domínio sozinho |
| `worker/flights-proxy.js` | Alternativa em Cloudflare Worker (preencher `PROXY` no index) |

## Camadas e fontes
- **Câmeras**: TfL Londres, Digitraffic Finlândia (exige `Accept-Encoding: gzip`), NYC DOT, Caltrans (distritos 1–12), DriveBC (`/api/webcams/`), NZTA, Iowa DOT (ArcGIS), **Road511** (api.road511.com, 20 estados dos EUA, sem chave). Fontes Road511/Iowa/NZTA vieram do projeto Argus (MIT). Resultado por fonte em `data/sources.json`. Ícone de câmera; ponto vermelho = tem vídeo. Botão "Ver ao vivo" toca mp4 ou HLS (hls.js 1.5.17) dentro do site; se falhar, volta para a imagem. 511 Ontário/Alberta removidos (exigem chave).
- **Voos** (live, zoom ≥ 6, a cada 15 s): adsb.lol (só via proxy, sem CORS) → airplanes.live → OpenSky. No GitHub Pages direto aparece "precisa do proxy" (nenhuma API de voos grátis libera CORS); hospedar na Vercel resolve via `api/flights.js`.
- **Satélites** (satellite.js 4.1.4, SGP4 no navegador, a cada 3 s): grupos stations, visual, gps-ops, weather, science, geo; **Starlink** em camada separada. Cor por categoria; toque abre ficha (velocidade, altitude, país, lançamento e local via SATCAT, idade, tipo de órbita, apogeu/perigeu, inclinação), órbita tracejada, círculo de cobertura e foto + resumo da Wikipédia (busca em inglês com atalhos `WIKI_ALIAS`, texto em pt quando houver). ~11,4 mil objetos, sendo ~10,6 mil Starlink.
- **Cabos submarinos**, **Aeroportos** (grandes/médios com voos regulares, só a partir do zoom 4), **Frente Ucrânia**: arquivos estáticos em `data/`.
- **Navios**: Digitraffic AIS (só cobre o Báltico; AIS global grátis exige chave).
- **Terremotos**: USGS M2.5+ 7 dias. **Eventos**: NASA EONET (incêndios, tempestades, vulcões).
- **Câmeras OSM** (zoom ≥ 10, até 4.000 por área) e **Usinas** (zoom ≥ 7): Overpass API.
- Mapa base: Esri World Dark Gray (Base + Reference). A CARTO passou a exigir chave e foi removida.
- Busca de local: Nominatim.
- **Ícones**: classe `Shape` (CircleMarker em canvas com formatos): navio = seta no rumo, terremoto = anel, evento = losango colorido por tipo, OSM = quadrado, usina = hexágono, satélite = corpo + painéis, aeroporto = cruz. Botões das camadas têm o mesmo ícone (`ICO`).

## Histórico
- 2026-11-23: versão inicial; corrigidos mapa base (CARTO → Esri), CSS dos clusters (faltava MarkerCluster.Default.css) e fontes de voos.
- 2026-11-23: adicionados satélites, Starlink, cabos, aeroportos, frente na Ucrânia, botão ⓘ de créditos e `api/flights.js`.
- 2026-11-23: ícones maiores em todas as camadas, canvas com tolerância de toque 10 px, satélites com ficha completa.
- 2026-11-23: ícones diferentes por camada, mais câmeras (Road511, Iowa, NZTA, correções Digitraffic/DriveBC), player de vídeo ao vivo, OSM a partir do zoom 10.
- Licenças: projeto pessoal e não comercial. airplanes.live, adsb.fi e OpenSky são só para uso não comercial; manter créditos (TfL, Digitraffic CC BY, cabos CC BY-NC-SA).
- Página hospedada como artifact do Claude não serve: a CSP bloqueia fetch externo e imagens remotas.

## Pendências
1. Voos: importar o repo na Vercel (vercel.com, login com GitHub) para ativar `api/flights.js`; o site passa a ser o endereço da Vercel.
2. Verificar quais camadas aparecem com erro (status em vermelho no botão).
3. Ideias: câmeras do Brasil (sem fonte aberta conhecida), Windy Webcams com chave opcional, AIS global (AISStream exige chave e servidor), outras frentes de guerra.

## Como testar localmente (feito pelo Claude)
O ambiente tem `/usr/bin/google-chrome`, mas os CDNs e as APIs são bloqueados. Instale via npm `leaflet@1.9.4 leaflet.markercluster@1.5.3 satellite.js@4.1.4 hls.js@1.5.17 puppeteer-core`, copie o `index.html` e `data/` para uma pasta, troque as URLs dos CDNs por `lib/`, sirva com `python3 -m http.server` e rode o puppeteer (viewport 400x820, mobile) para tirar screenshots e checar erros de JS.

## Observações de trabalho
- O ambiente do Claude não alcança essas APIs (allowlist), então os testes são feitos pelo dono no celular.
- Commits com o app do Claude instalado no GitHub (acesso só a este repo).
- O dono prefere poucas confirmações: fazer e informar.
