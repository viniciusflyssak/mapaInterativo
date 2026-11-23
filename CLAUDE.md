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
- **Câmeras** (~5.300 na 1ª execução): TfL Londres, Digitraffic Finlândia, NYC DOT, Caltrans (distritos 1–12), DriveBC, 511 Ontário, 511 Alberta. Imagem recarrega a cada 15 s; favoritos e grade no botão ★ (localStorage).
- **Voos** (live, zoom ≥ 6, a cada 15 s): adsb.lol (só via proxy, sem CORS) → airplanes.live → OpenSky. No GitHub Pages direto aparece "precisa do proxy" (nenhuma API de voos grátis libera CORS); hospedar na Vercel resolve via `api/flights.js`.
- **Satélites** (satellite.js 4.1.4, SGP4 no navegador, a cada 3 s): grupos stations, visual, gps-ops, weather, science, geo; **Starlink** em camada separada. Cor por categoria; toque abre ficha (velocidade, altitude, país, lançamento e local via SATCAT, idade, tipo de órbita, apogeu/perigeu, inclinação), órbita tracejada e círculo de cobertura. ~11,4 mil objetos, sendo ~10,6 mil Starlink.
- **Cabos submarinos**, **Aeroportos** (grandes/médios com voos regulares), **Frente Ucrânia**: arquivos estáticos em `data/`.
- **Navios**: Digitraffic AIS (só cobre o Báltico; AIS global grátis exige chave).
- **Terremotos**: USGS M2.5+ 7 dias. **Eventos**: NASA EONET (incêndios, tempestades, vulcões).
- **Câmeras OSM** (zoom ≥ 13) e **Usinas** (zoom ≥ 7): Overpass API.
- Mapa base: Esri World Dark Gray (Base + Reference). A CARTO passou a exigir chave e foi removida.
- Busca de local: Nominatim.

## Histórico
- 2026-11-23: versão inicial; corrigidos mapa base (CARTO → Esri), CSS dos clusters (faltava MarkerCluster.Default.css) e fontes de voos.
- 2026-11-23: adicionados satélites, Starlink, cabos, aeroportos, frente na Ucrânia, botão ⓘ de créditos e `api/flights.js`.
- 2026-11-23: ícones maiores em todas as camadas, canvas com tolerância de toque 10 px, satélites com ficha completa.
- Licenças: projeto pessoal e não comercial. airplanes.live, adsb.fi e OpenSky são só para uso não comercial; manter créditos (TfL, Digitraffic CC BY, cabos CC BY-NC-SA).
- Página hospedada como artifact do Claude não serve: a CSP bloqueia fetch externo e imagens remotas.

## Pendências
1. Voos: importar o repo na Vercel (vercel.com, login com GitHub) para ativar `api/flights.js`; o site passa a ser o endereço da Vercel.
2. Verificar quais camadas aparecem com erro (status em vermelho no botão).
3. Ideias: câmeras do Brasil (sem fonte aberta conhecida), Windy Webcams com chave opcional, AIS global (AISStream exige chave e servidor), outras frentes de guerra.

## Observações de trabalho
- O ambiente do Claude não alcança essas APIs (allowlist), então os testes são feitos pelo dono no celular.
- Commits com o app do Claude instalado no GitHub (acesso só a este repo).
- O dono prefere poucas confirmações: fazer e informar.
