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
| `.github/workflows/cameras.yml` | Roda o script a cada 6 h, manualmente ou em push nos scripts; faz commit do JSON |
| `data/cameras.json` | `[[lat, lon, nome, url_imagem, fonte, url_video], ...]`, gerado pela Action |
| `worker/flights-proxy.js` | Cloudflare Worker (proxy CORS) só para APIs de voos; **ainda não publicado** |

## Camadas e fontes
- **Câmeras** (~5.300 na 1ª execução): TfL Londres, Digitraffic Finlândia, NYC DOT, Caltrans (distritos 1–12), DriveBC, 511 Ontário, 511 Alberta. Imagem recarrega a cada 15 s; favoritos e grade no botão ★ (localStorage).
- **Voos** (live, zoom ≥ 6, a cada 15 s): adsb.lol (só via proxy, sem CORS) → airplanes.live → OpenSky. Constante `PROXY` no `index.html` fica vazia até o Worker existir.
- **Navios**: Digitraffic AIS (só cobre o Báltico; AIS global grátis exige chave).
- **Terremotos**: USGS M2.5+ 7 dias. **Eventos**: NASA EONET (incêndios, tempestades, vulcões).
- **Câmeras OSM** (zoom ≥ 13) e **Usinas** (zoom ≥ 7): Overpass API.
- Mapa base: Esri World Dark Gray (Base + Reference). A CARTO passou a exigir chave e foi removida.
- Busca de local: Nominatim.

## Histórico
- 2026-11-23: versão inicial; corrigidos mapa base (CARTO → Esri), CSS dos clusters (faltava MarkerCluster.Default.css) e fontes de voos.
- Página hospedada como artifact do Claude não serve: a CSP bloqueia fetch externo e imagens remotas.

## Pendências
1. Confirmar se voos funcionam direto (airplanes.live/OpenSky); se não, publicar `worker/flights-proxy.js` na Cloudflare e preencher `PROXY`.
2. Verificar quais camadas aparecem com erro (status em vermelho no botão).
3. Ideias: câmeras do Brasil (sem fonte aberta conhecida), Windy Webcams com chave opcional, AIS global (AISStream exige chave e servidor), fronts de guerra.

## Observações de trabalho
- O ambiente do Claude não alcança essas APIs (allowlist), então os testes são feitos pelo dono no celular.
- Commits com o app do Claude instalado no GitHub (acesso só a este repo).
- O dono prefere poucas confirmações: fazer e informar.
