// Mis Finanzas: servidor que conecta la app con tu base "Movimientos" de Notion.
//
// Variables que se configuran en Cloudflare (Settings -> Variables and Secrets):
//   NOTION_TOKEN  (secreto)  clave de la integración de Notion (empieza por ntn_)
//   APP_KEY       (secreto)  una clave tuya; va en el enlace de la app: ...workers.dev/?k=APP_KEY
//   DATABASE_ID   (texto)    id de la base Movimientos
//
// Este archivo se genera con build.py a partir de worker.template.js e ../index.html.
// Para cambiar la app edita esos archivos y vuelve a correr: python3 build.py

const APP_HTML = __APP_HTML__;

const NOTION = "https://api.notion.com/v1";
const NOTION_VERSION = "2022-06-28";
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
const ID_RE = /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i;
const SERIE_RE = /^[a-z0-9]{4,24}$/;
const TIPOS = ["Gasto", "Ingreso", "Inversión", "Transferencia", "Reembolso"];

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/" && request.method === "GET") return servePage(url, env);
      if (url.pathname.startsWith("/api/")) {
        if (!env.NOTION_TOKEN || !env.APP_KEY || !env.DATABASE_ID)
          return json({ error: "Falta configurar NOTION_TOKEN, APP_KEY o DATABASE_ID en Cloudflare" }, 500);
        if (!sameKey(request.headers.get("x-app-key") || "", env.APP_KEY))
          return json({ error: "Clave incorrecta" }, 401);
        return await route(request, url, env);
      }
      return new Response("No encontrado", { status: 404 });
    } catch (err) {
      return json({ error: err.message || "Error inesperado" }, err.status || 500);
    }
  },
};

function servePage(url, env) {
  const k = url.searchParams.get("k") || "";
  if (!env.APP_KEY || !sameKey(k, env.APP_KEY)) {
    return new Response(
      '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><body style="font:16px system-ui;padding:24px">' +
        "<h2>Mis Finanzas</h2><p>Este enlace no tiene la clave correcta. Abre la app con el enlace completo que termina en <code>?k=tu-clave</code>.</p>",
      { status: 401, headers: { "content-type": "text/html; charset=utf-8" } }
    );
  }
  const cfg = `<script>window.FIN_CONFIG={api:"/api",key:${JSON.stringify(k).replace(/</g, "\\u003c")}};</script>`;
  return new Response(APP_HTML.replace("</head>", cfg + "</head>"), {
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "referrer-policy": "no-referrer",
    },
  });
}

async function route(request, url, env) {
  const p = url.pathname, m = request.method;

  if (p === "/api/rows" && m === "GET") {
    const from = url.searchParams.get("from"), to = url.searchParams.get("to");
    if (!DATE_RE.test(from || "") || !DATE_RE.test(to || "")) return json({ error: "Fechas inválidas" }, 400);
    const filter = { and: [
      { property: "Fecha", date: { on_or_after: from } },
      { property: "Fecha", date: { on_or_before: to } },
    ] };
    const pages = await queryAll(env, filter, 30);
    return json({ rows: pages.map(fromPage).filter(Boolean) });
  }

  if (p === "/api/rows" && m === "POST") {
    const body = await readBody(request);
    const list = arr(body.rows, 25);
    const out = [];
    for (const r of list) {
      const page = await notion(env, "POST", "/pages", {
        parent: { database_id: env.DATABASE_ID },
        properties: toProps(r, true),
      });
      out.push(fromPage(page));
    }
    return json({ rows: out });
  }

  if (p === "/api/rows" && m === "PATCH") {
    const body = await readBody(request);
    const list = arr(body.updates, 25);
    for (const u of list) {
      if (!ID_RE.test(u.id || "")) throw httpError("Id inválido", 400);
      await notion(env, "PATCH", "/pages/" + u.id, { properties: toProps(u, false) });
    }
    return json({ ok: true });
  }

  if (p === "/api/rows/delete" && m === "POST") {
    const body = await readBody(request);
    const ids = arr(body.ids, 25);
    for (const id of ids) {
      if (!ID_RE.test(id || "")) throw httpError("Id inválido", 400);
      await notion(env, "PATCH", "/pages/" + id, { archived: true });
    }
    return json({ ok: true });
  }

  // Borra las filas de un ítem mensual (todas, o desde una fecha). Por partes, para no
  // pasar el límite de peticiones de Cloudflare; la app repite mientras "remaining" sea true.
  if (p === "/api/series/delete" && m === "POST") {
    const body = await readBody(request);
    if (!SERIE_RE.test(body.serie || "")) return json({ error: "Serie inválida" }, 400);
    const and = [{ property: "Serie", rich_text: { starts_with: body.serie + "|" } }];
    if (body.desde) {
      if (!DATE_RE.test(body.desde)) return json({ error: "Fecha inválida" }, 400);
      and.push({ property: "Fecha", date: { on_or_after: body.desde } });
    }
    const res = await notion(env, "POST", `/databases/${env.DATABASE_ID}/query`, { filter: { and }, page_size: 30 });
    for (const page of res.results) await notion(env, "PATCH", "/pages/" + page.id, { archived: true });
    return json({ deleted: res.results.length, remaining: !!res.has_more });
  }

  return json({ error: "Ruta no encontrada" }, 404);
}

/* ---------- Notion ---------- */
async function notion(env, method, path, body) {
  for (let attempt = 0; attempt < 4; attempt++) {
    const res = await fetch(NOTION + path, {
      method,
      headers: {
        authorization: "Bearer " + env.NOTION_TOKEN,
        "notion-version": NOTION_VERSION,
        "content-type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 429 && attempt < 3) {
      const wait = Math.min(Number(res.headers.get("retry-after")) || 1, 3);
      await new Promise((r) => setTimeout(r, wait * 1000));
      continue;
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = res.status === 401 ? "La clave de Notion (NOTION_TOKEN) no es válida"
        : res.status === 404 ? "Notion no encuentra la base. Conecta la integración a la página (••• → Conexiones)"
        : data.message || "Error de Notion " + res.status;
      throw httpError(msg, 502);
    }
    return data;
  }
}

async function queryAll(env, filter, maxPages) {
  const out = [];
  let cursor;
  for (let i = 0; i < maxPages; i++) {
    const res = await notion(env, "POST", `/databases/${env.DATABASE_ID}/query`, {
      filter, sorts: [{ property: "Fecha", direction: "ascending" }], page_size: 100,
      ...(cursor ? { start_cursor: cursor } : {}),
    });
    out.push(...res.results);
    if (!res.has_more) break;
    cursor = res.next_cursor;
  }
  return out;
}

const plain = (rt) => (rt || []).map((t) => t.plain_text).join("");

function fromPage(page) {
  const p = page.properties || {};
  const fecha = p["Fecha"]?.date?.start?.slice(0, 10);
  if (!fecha) return null;
  return {
    id: page.id,
    desc: plain(p["Descripción"]?.title) || "Sin descripción",
    tipo: p["Tipo"]?.select?.name || "Gasto",
    monto: Number(p["Monto"]?.number) || 0,
    fecha,
    cat: p["Categoría"]?.select?.name || "",
    met: p["Método de Pago"]?.select?.name || "",
    frec: p["Frecuencia"]?.select?.name === "Mensual" ? "mensual" : "unica",
    pagado: !!p["Pagado"]?.checkbox,
    serie: plain(p["Serie"]?.rich_text),
    omit: !!p["Omitido"]?.checkbox,
  };
}

const selectName = (v) => {
  const s = String(v || "").replace(/,/g, " ").trim().slice(0, 90);
  return s ? { select: { name: s } } : { select: null };
};

// Convierte una fila de la app en propiedades de Notion. Solo incluye los campos enviados.
function toProps(r, isNew) {
  const props = {};
  const has = (k) => isNew || Object.prototype.hasOwnProperty.call(r, k);
  if (has("desc")) props["Descripción"] = { title: [{ text: { content: String(r.desc || "Sin descripción").slice(0, 200) } }] };
  if (has("tipo")) {
    if (!TIPOS.includes(r.tipo)) throw httpError("Tipo inválido", 400);
    props["Tipo"] = { select: { name: r.tipo } };
  }
  if (has("monto")) {
    const n = Number(r.monto);
    if (!Number.isFinite(n) || n < 0 || n > 1e12) throw httpError("Monto inválido", 400);
    props["Monto"] = { number: n };
  }
  if (has("fecha")) {
    if (!DATE_RE.test(r.fecha || "")) throw httpError("Fecha inválida", 400);
    props["Fecha"] = { date: { start: r.fecha } };
  }
  if (has("cat")) props["Categoría"] = selectName(r.cat);
  if (has("met")) props["Método de Pago"] = selectName(r.met);
  if (isNew) props["Frecuencia"] = { select: { name: r.serie ? "Mensual" : "Una vez" } };
  if (has("pagado")) props["Pagado"] = { checkbox: !!r.pagado };
  if (has("omit")) props["Omitido"] = { checkbox: !!r.omit };
  if (has("serie")) {
    const s = String(r.serie || "").slice(0, 60);
    props["Serie"] = { rich_text: s ? [{ text: { content: s } }] : [] };
  }
  return props;
}

/* ---------- Utilidades ---------- */
function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}
function httpError(message, status) { const e = new Error(message); e.status = status; return e; }
async function readBody(request) {
  try { return await request.json(); } catch { throw httpError("Cuerpo inválido", 400); }
}
function arr(v, max) {
  if (!Array.isArray(v) || v.length > max) throw httpError("Lista inválida", 400);
  return v;
}
function sameKey(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
