# ============================================================
# ValuaClick Backend v2.0 — FastAPI + Apify (Inmuebles24 real)
# Metodología: Comparativa de mercado + Factor ajuste 0.95
# JABES Avalúos y Proyectos SC — valuaclick.mx
# ============================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio, httpx, os, statistics

APIFY_TOKEN  = os.getenv("APIFY_TOKEN", "")
OPENAI_KEY   = os.getenv("OPENAI_API_KEY", "")
ACTOR_ID     = "ecomscrape~inmuebles24-property-listings-scraper"
FACTOR_AJUSTE = 0.95  # Factor de negociación IMV

app = FastAPI(title="ValuaClick API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchParams(BaseModel):
    operacion:  str
    tipo:       str
    recamaras:  int = 0
    ciudad:     str
    colonia:    Optional[str] = ""
    precio_min: float
    precio_max: float
    superficie: Optional[float] = 0
    altura:     Optional[float] = 0

def sl(s: str) -> str:
    import unicodedata, re
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

T1 = {
    "casa":"casas","departamento":"departamentos","terreno":"terrenos",
    "oficina":"oficinas","local":"locales-comerciales","bodega":"bodegas"
}

async def buscar_apify(params: SearchParams) -> list:
    """Busca en Inmuebles24 via Apify y retorna comparables reales"""
    if not APIFY_TOKEN:
        return []

    zona  = sl(params.colonia) if params.colonia else sl(params.ciudad)
    tipo  = T1.get(params.tipo, "casas")
    op    = params.operacion
    url   = f"https://www.inmuebles24.com/{tipo}-en-{op}-en-{zona}.html"

    # Ejecutar el Actor de Apify
    try:
        async with httpx.AsyncClient(timeout=60) as c:
            # 1. Iniciar el run
            run_resp = await c.post(
                f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs",
                params={"token": APIFY_TOKEN},
                json={
                    "startUrls": [{"url": url}],
                    "maxItems": 20,
                    "proxyConfiguration": {"useApifyProxy": True}
                }
            )
            if run_resp.status_code not in (200, 201):
                print(f"[Apify] Error al iniciar run: {run_resp.status_code}")
                return []

            run_data = run_resp.json()
            run_id   = run_data.get("data", {}).get("id")
            if not run_id:
                return []

            # 2. Esperar a que termine (máx 50 seg)
            for _ in range(10):
                await asyncio.sleep(5)
                status_resp = await c.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    params={"token": APIFY_TOKEN}
                )
                status = status_resp.json().get("data", {}).get("status", "")
                if status in ("SUCCEEDED", "FAILED", "ABORTED"):
                    break

            if status != "SUCCEEDED":
                print(f"[Apify] Run terminó con status: {status}")
                return []

            # 3. Obtener resultados
            dataset_id = status_resp.json().get("data", {}).get("defaultDatasetId")
            items_resp = await c.get(
                f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                params={"token": APIFY_TOKEN, "format": "json"}
            )
            items = items_resp.json()

    except Exception as e:
        print(f"[Apify] Error: {e}")
        return []

    # 4. Normalizar resultados
    comparables = []
    for item in items:
        try:
            # Extraer precio
            precio_raw = item.get("price") or item.get("precio") or 0
            if isinstance(precio_raw, str):
                precio_raw = "".join(filter(lambda x: x.isdigit(), precio_raw))
            precio = float(precio_raw) if precio_raw else 0
            if precio <= 0:
                continue
            if not (params.precio_min * 0.5 <= precio <= params.precio_max * 1.5):
                continue

            # Extraer metros
            metros = float(item.get("surface") or item.get("size") or
                          item.get("totalArea") or item.get("metros") or 0)

            precio_m2 = round(precio / max(metros, 1)) if metros > 0 else 0

            comparables.append({
                "portal":    "Inmuebles24",
                "titulo":    item.get("title") or item.get("name") or "",
                "precio":    precio,
                "metros":    metros,
                "precio_m2": precio_m2,
                "recamaras": item.get("rooms") or item.get("bedrooms") or params.recamaras,
                "antiguedad": 10,
                "colonia":   params.colonia or params.ciudad,
                "ciudad":    params.ciudad,
                "url":       item.get("url") or "#",
                "score":     0,
            })
        except Exception as e:
            print(f"[Apify] Error normalizando item: {e}")
            continue

    return comparables

def calcular_promedio_mercado(comparables: list, params: SearchParams) -> dict:
    """
    Metodología comparativa IMV:
    1. Filtrar outliers (IQR)
    2. Calcular promedio de precio/m²
    3. Aplicar factor de ajuste 0.95
    """
    if not comparables:
        return {}

    precios = [r["precio"] for r in comparables if r["precio"] > 0]
    if len(precios) < 3:
        return {}

    # Filtrar outliers con IQR
    q1 = statistics.quantiles(precios, n=4)[0]
    q3 = statistics.quantiles(precios, n=4)[2]
    iqr = q3 - q1
    precios_filtrados = [p for p in precios if q1 - 1.5*iqr <= p <= q3 + 1.5*iqr]

    if not precios_filtrados:
        precios_filtrados = precios

    promedio_bruto = statistics.mean(precios_filtrados)
    promedio_ajustado = round(promedio_bruto * FACTOR_AJUSTE)

    return {
        "promedio_bruto":    round(promedio_bruto),
        "promedio_ajustado": promedio_ajustado,
        "factor_ajuste":     FACTOR_AJUSTE,
        "total_comparables": len(precios_filtrados),
        "precio_min":        round(min(precios_filtrados)),
        "precio_max":        round(max(precios_filtrados)),
    }

def seleccionar_tres(comparables: list, mercado: dict, params: SearchParams) -> dict:
    """Selecciona 3 opciones estratégicas basadas en datos reales"""
    if not comparables or not mercado:
        return {}

    prom = mercado["promedio_ajustado"]

    def score(r):
        s = 0
        ratio = r["precio"] / max(prom, 1)
        s += min(40, max(0, 40*(1-(ratio-0.8)/0.4)))
        if r.get("metros", 0) > 0: s += 20
        if r.get("url", "#") != "#": s += 15
        s += 25  # base
        return round(s)

    for r in comparables:
        r["score"] = score(r)

    ordenados = sorted(comparables, key=lambda x: x["precio"], reverse=True)

    # Premium: top 30% de precio
    umbral_premium = prom * 1.15
    premium_cands = [r for r in comparables if r["precio"] >= umbral_premium]
    premium = max(premium_cands, key=lambda x: x["score"]) if premium_cands else ordenados[0]

    # Promedio: más cercano al promedio ajustado
    promedio = min(comparables, key=lambda x: abs(x["precio"] - prom))

    # Oportunidad: 15-20% por debajo del promedio
    limite_sup = prom * 0.85
    limite_inf = prom * 0.70
    opor_cands = [r for r in comparables if limite_inf <= r["precio"] <= limite_sup]
    oportunidad = max(opor_cands, key=lambda x: x["score"]) if opor_cands else ordenados[-1]

    return {
        "premium":     premium,
        "promedio":    promedio,
        "oportunidad": oportunidad,
    }

async def descripcion_ia(r: dict, ctx: str, params: SearchParams, mercado: dict) -> str:
    """Genera descripción con lenguaje de perito valuador"""
    if not OPENAI_KEY:
        diff = round((r["precio"] / max(mercado.get("promedio_ajustado", 1), 1) - 1) * 100)
        signo = "+" if diff >= 0 else ""
        return (
            f"{params.tipo.capitalize()} en {r['colonia']}, {params.ciudad}. "
            f"Precio {signo}{diff}% respecto al promedio ajustado de mercado "
            f"(factor negociación {mercado.get('factor_ajuste', 0.95)}). "
            f"Análisis basado en {mercado.get('total_comparables', 0)} comparables reales de Inmuebles24."
        )
    try:
        roles = {
            "premium":    "inmueble de precio elevado con alta plusvalía",
            "promedio":   "inmueble representativo del valor típico de mercado",
            "oportunidad":"inmueble por debajo del promedio — oportunidad de inversión"
        }
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_KEY}", "Content-Type": "application/json"},
                json={"model":"gpt-4o-mini","max_tokens":130,"messages":[
                    {"role":"system","content":"Perito valuador inmobiliario México (IMV/CIVEVAC). 3 oraciones técnicas en español. Sin bullets ni emojis."},
                    {"role":"user","content":
                        f"Tipo: {roles[ctx]}\n"
                        f"{params.tipo} en {params.operacion} · {r['colonia']}, {params.ciudad}\n"
                        f"Precio: ${r['precio']:,.0f} MXN | Promedio ajustado zona: ${mercado['promedio_ajustado']:,.0f} MXN\n"
                        f"Factor ajuste aplicado: {mercado['factor_ajuste']} | Comparables: {mercado['total_comparables']}\n"
                        f"Superficie: {r['metros']}m² | Precio/m²: ${r['precio_m2']:,}"
                    }
                ]}
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
    except:
        return f"{params.tipo.capitalize()} en {r['colonia']}, {params.ciudad}. Precio ${r['precio']:,.0f} MXN."

@app.post("/buscar")
async def buscar(params: SearchParams):
    # 1. Buscar comparables reales en Apify/Inmuebles24
    comparables = await buscar_apify(params)

    # 2. Calcular promedio de mercado con metodología IMV
    mercado = calcular_promedio_mercado(comparables, params)

    if not mercado or len(comparables) < 3:
        return {
            "status": "sin_datos_reales",
            "mensaje": "No se encontraron suficientes comparables reales. Use el simulador.",
            "total": len(comparables)
        }

    # 3. Seleccionar 3 opciones estratégicas
    tres = seleccionar_tres(comparables, mercado, params)
    if not tres:
        return {"status": "sin_resultados", "total": 0}

    # 4. Generar descripciones IA en paralelo
    ctxs = ["premium", "promedio", "oportunidad"]
    descs = await asyncio.gather(*[
        descripcion_ia(tres[ctx], ctx, params, mercado)
        for ctx in ctxs if ctx in tres
    ], return_exceptions=True)

    for i, ctx in enumerate(ctxs):
        if ctx in tres and i < len(descs) and isinstance(descs[i], str):
            tres[ctx]["descripcion_ia"] = descs[i]

    return {
        "status":            "ok",
        "total":             mercado["total_comparables"],
        "precio_promedio":   mercado["promedio_ajustado"],
        "precio_bruto":      mercado["promedio_bruto"],
        "factor_ajuste":     mercado["factor_ajuste"],
        "premium":           tres.get("premium"),
        "promedio":          tres.get("promedio"),
        "oportunidad":       tres.get("oportunidad"),
    }

@app.get("/health")
def health():
    return {
        "status":   "ValuaClick API activa",
        "version":  "2.0.0",
        "portal":   "valuaclick.mx",
        "empresa":  "JABES Avalúos y Proyectos SC",
        "apify":    "conectado" if APIFY_TOKEN else "sin token",
        "openai":   "conectado" if OPENAI_KEY else "sin token",
    }  
