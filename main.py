# ============================================================
# ValuaClick Backend — FastAPI + Scraping Real
# Valuación Inmobiliaria Inteligente con un Click
# JABES Avalúos y Proyectos SC — valuaclick.mx
# ============================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio, httpx, os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

app = FastAPI(title="ValuaClick API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    "Accept-Language": "es-MX,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

class SearchParams(BaseModel):
    operacion:  str
    tipo:       str
    recamaras:  int
    ciudad:     str
    colonia:    Optional[str] = ""
    precio_min: float
    precio_max: float

def sl(s: str) -> str:
    import unicodedata, re
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")

T1 = {"casa":"casas","departamento":"departamentos","terreno":"terrenos","oficina":"oficinas","local":"locales-comerciales"}

async def scrape_propiedades(p: SearchParams) -> list:
    zona  = sl(p.colonia)+"-"+sl(p.ciudad) if p.colonia else sl(p.ciudad)
    tipo  = T1.get(p.tipo, "casas")
    url   = f"https://propiedades.com/{zona}/{tipo}-{p.operacion}"
    items = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12, follow_redirects=True) as c:
            r = await c.get(url)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser")
            tarjetas = soup.select("[data-id]") or soup.select("article") or soup.select("[class*='property']")
            for t in tarjetas[:12]:
                try:
                    precio_el = t.select_one("[class*='price']") or t.select_one("[class*='precio']")
                    link_el   = t.select_one("a[href]")
                    metros_el = t.select_one("[class*='area']") or t.select_one("[class*='metros']")
                    if not precio_el: continue
                    raw = "".join(filter(lambda x: x.isdigit() or x==".", precio_el.get_text()))
                    precio = float(raw.replace(",","")) if raw else 0
                    if not (p.precio_min <= precio <= p.precio_max): continue
                    metros_raw = "".join(filter(lambda x: x.isdigit() or x==".", metros_el.get_text())) if metros_el else "0"
                    href = link_el.get("href","") if link_el else ""
                    full_url = href if href.startswith("http") else f"https://propiedades.com{href}"
                    items.append({
                        "portal":"Propiedades.com","titulo":t.get_text(separator=" ",strip=True)[:80],
                        "precio":precio,"metros":float(metros_raw) if metros_raw else 0,
                        "recamaras":p.recamaras,"antiguedad":10,"colonia":p.colonia or p.ciudad,
                        "url":full_url,"precio_m2":round(precio/max(float(metros_raw) if metros_raw else 1,1)),
                    })
                except: continue
    except Exception as e:
        print(f"[Propiedades] {e}")
    return items

async def scrape_inmuebles24(p: SearchParams) -> list:
    zona = sl(p.colonia) if p.colonia else sl(p.ciudad)
    tipo = T1.get(p.tipo, "casas")
    url  = f"https://www.inmuebles24.com/{tipo}-en-{p.operacion}-en-{zona}.html"
    items = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12, follow_redirects=True) as c:
            r = await c.get(url)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser")
            tarjetas = soup.select("[data-testid='posting-card-container']") or soup.select("article")
            for t in tarjetas[:12]:
                try:
                    precio_el = t.select_one("[data-testid='posting-price']") or t.select_one("[class*='price']")
                    link_el   = t.select_one("a[href]")
                    metros_el = t.select_one("[data-testid='surface']") or t.select_one("[class*='surface']")
                    if not precio_el: continue
                    raw = "".join(filter(str.isdigit, precio_el.get_text()))
                    precio = float(raw) if raw else 0
                    if not (p.precio_min <= precio <= p.precio_max): continue
                    metros_raw = "".join(filter(lambda x: x.isdigit() or x==".", metros_el.get_text())) if metros_el else "0"
                    href = link_el.get("href","") if link_el else ""
                    full_url = f"https://www.inmuebles24.com{href}" if href.startswith("/") else href
                    items.append({
                        "portal":"Inmuebles24","titulo":t.get_text(separator=" ",strip=True)[:80],
                        "precio":precio,"metros":float(metros_raw) if metros_raw else 0,
                        "recamaras":p.recamaras,"antiguedad":8,"colonia":p.colonia or p.ciudad,
                        "url":full_url,"precio_m2":round(precio/max(float(metros_raw) if metros_raw else 1,1)),
                    })
                except: continue
    except Exception as e:
        print(f"[Inmuebles24] {e}")
    return items

async def scrape_vivanuncios(p: SearchParams) -> list:
    tipo = T1.get(p.tipo, "casas")
    zona = sl(p.colonia or p.ciudad)
    url  = f"https://www.vivanuncios.com.mx/s-{tipo}-{p.operacion}/{zona}/"
    items = []
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=12, follow_redirects=True) as c:
            r = await c.get(url)
            if r.status_code != 200: return []
            soup = BeautifulSoup(r.text, "html.parser")
            tarjetas = soup.select("[class*='ad-listing']") or soup.select("article")
            for t in tarjetas[:10]:
                try:
                    precio_el = t.select_one("[class*='price']")
                    link_el   = t.select_one("a[href]")
                    if not precio_el: continue
                    raw = "".join(filter(str.isdigit, precio_el.get_text()))
                    precio = float(raw) if raw else 0
                    if not (p.precio_min <= precio <= p.precio_max): continue
                    href = link_el.get("href","") if link_el else ""
                    full_url = href if href.startswith("http") else f"https://www.vivanuncios.com.mx{href}"
                    items.append({
                        "portal":"Vivanuncios","titulo":t.get_text(separator=" ",strip=True)[:80],
                        "precio":precio,"metros":0,"recamaras":p.recamaras,"antiguedad":10,
                        "colonia":p.colonia or p.ciudad,"url":full_url,"precio_m2":0,
                    })
                except: continue
    except Exception as e:
        print(f"[Vivanuncios] {e}")
    return items

def calcular_score(r: dict, p: SearchParams) -> float:
    score = 0.0
    prom  = (p.precio_min + p.precio_max) / 2
    metros = max(r.get("metros",1),1)
    pm2    = r.get("precio_m2") or round(r["precio"]/metros)
    ratio  = pm2 / max(prom/metros,1)
    score += min(40, max(0, 40*(1-(ratio-0.8)/0.4)))
    edad = r.get("antiguedad",15)
    if   edad<=5:  score+=30
    elif edad<=10: score+=22
    elif edad<=15: score+=14
    else:          score+=8
    rec = r.get("recamaras",0)
    if   rec==p.recamaras:            score+=15
    elif abs(rec-p.recamaras)==1:     score+=8
    if r.get("metros",0)>0:           score+=8
    if r.get("url","").startswith("http"): score+=7
    return round(score,1)

def seleccionar_tres(todos: list, p: SearchParams) -> dict:
    if not todos: return {}
    rango = p.precio_max - p.precio_min
    prom  = p.precio_min + rango*0.5
    def mejor(cands): return max(cands, key=lambda x: x["score"]) if cands else None
    premium    = mejor([r for r in todos if r["precio"] >= p.precio_min+rango*0.70])
    promedio   = mejor([r for r in todos if p.precio_min+rango*0.35 <= r["precio"] <= p.precio_min+rango*0.65])
    oportunidad= mejor([r for r in todos if r["precio"] <= p.precio_min+rango*0.35])
    ordenados  = sorted(todos, key=lambda x: x["precio"], reverse=True)
    if not premium:     premium    = ordenados[0]
    if not promedio:    promedio   = min(todos, key=lambda x: abs(x["precio"]-prom))
    if not oportunidad: oportunidad= ordenados[-1]
    return {"premium":premium,"promedio":promedio,"oportunidad":oportunidad,
            "total":len(todos),"precio_promedio":round(prom)}

async def generar_descripcion(r: dict, ctx: str, p: SearchParams) -> str:
    roles = {
        "premium":    "inmueble de precio elevado con alta plusvalía",
        "promedio":   "inmueble que representa el valor típico de mercado",
        "oportunidad":"inmueble por debajo del promedio — oportunidad de inversión"
    }
    if not OPENAI_KEY:
        diff = round((r["precio"]/max((p.precio_min+p.precio_max)/2,1)-1)*100)
        signo = "+" if diff>=0 else ""
        return (f"{p.tipo.capitalize()} en {r['colonia']}, {p.ciudad}. "
                f"Precio {signo}{diff}% respecto al promedio de zona a ${r['precio_m2']:,}/m². "
                f"Score valuatorio ValuaClick: {r['score']}/100.")
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            resp = await c.post("https://api.openai.com/v1/chat/completions",
                headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
                json={"model":"gpt-4o-mini","max_tokens":120,"messages":[
                    {"role":"system","content":"Perito valuador inmobiliario México (IMV/CIVEVAC/JABES). 3 oraciones técnicas en español. Sin bullets ni emojis."},
                    {"role":"user","content":
                        f"Tipo: {roles[ctx]}\n"
                        f"{p.tipo} {p.operacion} en {r['colonia']}, {p.ciudad}\n"
                        f"Precio: ${r['precio']:,.0f} MXN | {r['metros']}m² | ${r['precio_m2']:,}/m²\n"
                        f"Recámaras: {r['recamaras']} | Antigüedad: {r['antiguedad']} años | Score ValuaClick: {r['score']}/100"
                    }
                ]}
            )
            return resp.json()["choices"][0]["message"]["content"].strip()
    except:
        return f"Inmueble en {r['colonia']}, {p.ciudad}. Precio ${r['precio']:,.0f} MXN a ${r['precio_m2']:,}/m². Score ValuaClick {r['score']}/100."

@app.post("/buscar")
async def buscar(params: SearchParams):
    grupos = await asyncio.gather(
        scrape_propiedades(params),
        scrape_inmuebles24(params),
        scrape_vivanuncios(params),
        return_exceptions=True
    )
    todos = []
    for g in grupos:
        if isinstance(g, list): todos.extend(g)
    for r in todos:
        r["score"] = calcular_score(r, params)
    tres = seleccionar_tres(todos, params)
    if not tres:
        return {"status":"sin_resultados","mensaje":"No se encontraron inmuebles. Amplíe criterios.","total":0}
    ctxs  = ["premium","promedio","oportunidad"]
    descs = await asyncio.gather(*[generar_descripcion(tres[ctx],ctx,params) for ctx in ctxs if ctx in tres], return_exceptions=True)
    for i,ctx in enumerate(ctxs):
        if ctx in tres and i<len(descs) and isinstance(descs[i],str):
            tres[ctx]["descripcion_ia"] = descs[i]
    return {"status":"ok","total":tres["total"],"precio_promedio":tres["precio_promedio"],
            "premium":tres.get("premium"),"promedio":tres.get("promedio"),"oportunidad":tres.get("oportunidad")}

@app.get("/health")
def health():
    return {"status":"ValuaClick API activa","version":"1.0.0","portal":"valuaclick.mx","empresa":"JABES Avalúos y Proyectos SC"}
