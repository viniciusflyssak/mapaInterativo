// Função serverless (Vercel) que repassa as APIs de voos com CORS liberado.
// Hospedando o projeto na Vercel, o mapa usa /api/flights automaticamente.
const ALLOWED = ['api.adsb.lol', 'api.airplanes.live', 'opendata.adsb.fi', 'opensky-network.org'];

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  let target;
  try { target = new URL(req.query.url); } catch { return res.status(400).json({ error: 'url inválida' }); }
  if (target.protocol !== 'https:' || !ALLOWED.includes(target.hostname)) return res.status(403).json({ error: 'host não permitido' });
  try {
    const r = await fetch(target, { headers: { 'User-Agent': 'Mirante/1.0' } });
    res.setHeader('Cache-Control', 's-maxage=5, stale-while-revalidate=10');
    res.status(r.status).setHeader('Content-Type', 'application/json').send(await r.text());
  } catch (e) {
    res.status(502).json({ error: 'falha na fonte' });
  }
}
