from fastapi import FastAPI, Depends, HTTPException, status, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
import stripe
import json
import os
import logging

from models import Base, User, SearchLog, StripeEvent, SubscriptionPlan
from auth import (
    verify_password, get_password_hash, create_user_token, 
    get_current_user, TokenData, Token, create_access_token
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/valuaclick")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Database
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

# Stripe
stripe.api_key = STRIPE_SECRET_KEY

# FastAPI app
app = FastAPI(title="ValuaClick API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# SCHEMAS
# ============================================================================

class SearchRequest(BaseModel):
    query: str
    portales: Optional[list] = None  # ['inmuebles24', 'vivanuncios', etc]

class SearchResponse(BaseModel):
    results: list
    remaining_searches: int
    blocked: bool
    message: str = None

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    subscription_plan: str
    search_count: int
    remaining_free_searches: int
    can_search: bool

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ============================================================================
# AUTENTICACIÓN
# ============================================================================

@app.post("/api/auth/register", response_model=Token)
async def register(data: CreateUserRequest, db: Session = Depends(get_db)):
    """Registra nuevo usuario con email/contraseña"""
    
    # Verificar si existe
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    
    # Crear usuario
    hashed_pwd = get_password_hash(data.password)
    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hashed_pwd,
        oauth_provider="email",
        subscription_plan=SubscriptionPlan.FREE
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return create_user_token(user.id, user.email)


@app.post("/api/auth/login", response_model=Token)
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Login con email/contraseña"""
    
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Email o contraseña inválidos")
    
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email o contraseña inválidos")
    
    return create_user_token(user.id, user.email)


@app.post("/api/auth/google", response_model=Token)
async def google_auth(token: str, db: Session = Depends(get_db)):
    """Login/Registro con Google OAuth"""
    # En producción, verificar el token de Google
    # Este es un placeholder - implementar con google-auth-oauthlib
    
    from google.auth.transport import requests
    from google.oauth2 import id_token
    
    try:
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            os.getenv("GOOGLE_CLIENT_ID")
        )
        
        email = idinfo['email']
        name = idinfo.get('name', '')
        google_id = idinfo['sub']
        
        # Buscar usuario
        user = db.query(User).filter(User.google_id == google_id).first()
        
        if not user:
            # Crear nuevo usuario
            user = User(
                email=email,
                full_name=name,
                google_id=google_id,
                oauth_provider="google",
                subscription_plan=SubscriptionPlan.FREE
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        return create_user_token(user.id, user.email)
    
    except Exception as e:
        logger.error(f"Google auth error: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google token")


# ============================================================================
# USUARIO
# ============================================================================

@app.get("/api/user/me", response_model=UserResponse)
async def get_me(token_data: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    """Obtiene datos del usuario autenticado"""
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        subscription_plan=user.subscription_plan,
        search_count=user.search_count,
        remaining_free_searches=int(user.remaining_free_searches()),
        can_search=user.can_search()
    )


# ============================================================================
# BÚSQUEDAS
# ============================================================================

@app.post("/api/search", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    token_data: Optional[TokenData] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Ejecuta búsqueda con limitación según plan"""
    
    user = None
    if token_data:
        user = db.query(User).filter(User.id == token_data.user_id).first()
    
    # Verificar si puede buscar
    if user:
        if not user.can_search():
            return SearchResponse(
                results=[],
                remaining_searches=0,
                blocked=True,
                message="Límite de búsquedas alcanzado. Suscríbete para acceso ilimitado.",
                upgrade_url="/pricing"
            )
    else:
        # Usuario anónimo - máximo 2 búsquedas por sesión
        return SearchResponse(
            results=[],
            remaining_searches=0,
            blocked=True,
            message="Crea una cuenta para buscar. Obtén 2 búsquedas gratuitas."
        )
    
    # Ejecutar búsqueda (aquí iría tu lógica de Apify + scraping)
    try:
        results = await execute_search(req.query, req.portales or [])
    except Exception as e:
        logger.error(f"Search error: {e}")
        results = []
    
    # Registrar búsqueda
    search_log = SearchLog(
        user_id=user.id if user else None,
        query=req.query,
        portales_searched=json.dumps(req.portales or []),
        result_count=len(results)
    )
    db.add(search_log)
    
    # Incrementar contador
    user.search_count += 1
    user.last_search_date = datetime.utcnow()
    db.commit()
    
    return SearchResponse(
        results=results,
        remaining_searches=int(max(0, 2 - user.search_count)) if user.subscription_plan == SubscriptionPlan.FREE else 999,
        blocked=False,
        message="Búsqueda exitosa"
    )


async def execute_search(query: str, portales: list):
    """Ejecuta búsqueda real (conectar con Apify)"""
    # PLACEHOLDER: implementar lógica de scraping
    # Por ahora retorna resultados mock
    return [
        {
            "id": 1,
            "title": f"Resultado para: {query}",
            "price": "$500,000",
            "location": "Boca del Río, Veracruz",
            "portal": "inmuebles24"
        }
    ]


# ============================================================================
# SUSCRIPCIÓN / STRIPE
# ============================================================================

class CheckoutSessionRequest(BaseModel):
    plan: str  # 'agente', 'despacho', 'institucional'

@app.post("/api/subscription/checkout")
async def create_checkout_session(
    req: CheckoutSessionRequest,
    token_data: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crea sesión de checkout en Stripe"""
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Precios de planes (debes configurar en Stripe Dashboard)
    plans = {
        "agente": "price_agente_valuaclick",
        "despacho": "price_despacho_valuaclick",
        "institucional": "price_institucional_valuaclick"
    }
    
    if req.plan not in plans:
        raise HTTPException(status_code=400, detail="Plan inválido")
    
    try:
        # Crear sesión de checkout
        session = stripe.checkout.Session.create(
            customer_email=user.email,
            payment_method_types=["card"],
            line_items=[{
                "price": plans[req.plan],
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{FRONTEND_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/pricing",
            metadata={
                "user_id": str(user.id),
                "plan": req.plan
            }
        )
        
        return {"checkout_url": session.url, "session_id": session.id}
    
    except Exception as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=500, detail="Error creando sesión de pago")


@app.post("/api/webhook/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: Session = Depends(get_db)
):
    """Webhook para eventos de Stripe"""
    
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="No signature")
    
    try:
        event = stripe.Webhook.construct_event(
            await request.body(),
            stripe_signature,
            STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Procesar evento
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session["metadata"]["user_id"])
        plan = session["metadata"]["plan"]
        
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.subscription_plan = plan
            user.subscription_id = session["subscription"]
            
            # Establecer fecha de expiración (30 días)
            user.subscription_expires = datetime.utcnow() + timedelta(days=30)
            user.search_count = 0  # Reset contador
            
            db.commit()
            logger.info(f"User {user_id} upgraded to {plan}")
    
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        user = db.query(User).filter(User.subscription_id == subscription["id"]).first()
        if user:
            user.subscription_plan = SubscriptionPlan.FREE
            user.subscription_expires = None
            user.search_count = 0
            db.commit()
            logger.info(f"User {user.id} subscription cancelled")
    
    # Guardar evento
    stripe_event = StripeEvent(
        event_id=event["id"],
        event_type=event["type"],
        data=json.dumps(event["data"]),
        processed=True
    )
    db.add(stripe_event)
    db.commit()
    
    return {"status": "success"}


@app.get("/api/subscription/status")
async def get_subscription_status(
    token_data: TokenData = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Obtiene estado de suscripción"""
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return {
        "plan": user.subscription_plan,
        "is_active": user.is_subscription_active(),
        "expires_at": user.subscription_expires,
        "search_count": user.search_count,
        "remaining_searches": int(user.remaining_free_searches())
    }


# ============================================================================
# HEALTH & INFO
# ============================================================================

@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/pricing")
async def pricing():
    """Obtiene planes y precios"""
    return {
        "plans": [
            {
                "id": "agente",
                "name": "Plan Agente",
                "price": 150,
                "currency": "MXN",
                "period": "monthly",
                "features": [
                    "Búsquedas ilimitadas",
                    "Acceso a todos los portales",
                    "Análisis básico",
                    "Soporte por email"
                ]
            },
            {
                "id": "despacho",
                "name": "Plan Despacho",
                "price": 300,
                "currency": "MXN",
                "period": "monthly",
                "features": [
                    "Búsquedas ilimitadas",
                    "Acceso a todos los portales",
                    "Análisis avanzado",
                    "Reportes PDF",
                    "Soporte prioritario"
                ]
            },
            {
                "id": "institucional",
                "name": "Plan Institucional",
                "price": 1000,
                "currency": "MXN",
                "period": "monthly",
                "features": [
                    "Búsquedas ilimitadas",
                    "Acceso a todos los portales",
                    "Análisis enterprise",
                    "API custom",
                    "Soporte 24/7"
                ]
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
