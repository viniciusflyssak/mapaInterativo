// Proxy mínimo para o Mirante (Cloudflare Worker, plano gratuito).
// Repassa só para as APIs de voos listadas e adiciona o cabeçalho CORS.
const ALLOWED = ['api.adsb.lol', 'api.airplanes.live', 'opensky-network.org'];

export default {
  async fetch(request) {
    const cors = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, OPTIONS' };
    if (request.method === 'OPTIONS') return new Response(null, { headers: cors });
    let target;
    try { target = new URL(new URL(request.url).searchParams.get('url')); } catch { return new Response('url inválida', { status: 400, headers: cors }); }
    if (target.protocol !== 'https:' || !ALLOWED.includes(target.hostname)) return new Response('host não permitido', { status: 403, headers: cors });
    const r = await fetch(target, { headers: { 'User-Agent': 'Mirante/1.0' }, cf: { cacheTtl: 5 } });
    return new Response(r.body, { status: r.status, headers: { ...cors, 'Content-Type': 'application/json', 'Cache-Control': 'public, max-age=5' } });
  },
};
