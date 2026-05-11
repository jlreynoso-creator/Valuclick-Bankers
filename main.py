from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
import stripe
import os
import logging

# Configuración
SECRET_KEY = os.getenv("SECRET_KEY", "tu-clave-secreta-super-segura-cambiar-en-produccion")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 43200
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_default")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(
    title="ValuaClick API",
    description="API para búsqueda y agregación de propiedades inmobiliarias",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ===== HEALTH CHECK =====
@app.get("/health")
def health_check():
    """Endpoint para verificar que el servidor está activo"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "service": "valuaclick-api"
    }

# ===== SCHEMAS =====
class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: str
    password: str

class SearchRequest(BaseModel):
    query: str
    location: Optional[str] = None

# ===== UTILIDADES =====
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contraseña contra su hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Genera un hash de contraseña"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Crea un JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ===== ENDPOINTS =====

@app.post("/api/auth/register")
async def register(user: UserRegister):
    """Registra un nuevo usuario"""
    return {
        "message": "Usuario registrado exitosamente",
        "email": user.email,
        "name": user.name
    }

@app.post("/api/auth/login")
async def login(user: UserLogin):
    """Login de usuario"""
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(days=30)
    )
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@app.get("/api/user/me")
async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Obtiene información del usuario actual"""
    return {
        "email": "user@example.com",
        "subscription_plan": "free",
        "search_count": 0,
        "remaining_free_searches": 2,
        "can_search": True
    }

@app.post("/api/search")
async def search(request: SearchRequest):
    """Realiza una búsqueda de propiedades"""
    return {
        "results": [],
        "remaining_searches": 1,
        "blocked": False,
        "message": "Búsqueda exitosa"
    }

@app.post("/api/subscription/checkout")
async def create_checkout_session(plan: str):
    """Crea una sesión de Stripe Checkout"""
    return {
        "checkout_url": "https://checkout.stripe.com/pay/example",
        "session_id": "sess_example"
    }

@app.get("/api/subscription/status")
async def subscription_status():
    """Obtiene el estado de la suscripción del usuario"""
    return {
        "subscription_plan": "free",
        "status": "active",
        "next_billing_date": None
    }

@app.get("/api/pricing")
async def get_pricing():
    """Obtiene los planes de precios disponibles"""
    return {
        "plans": [
            {
                "name": "Plan Agente",
                "price": 150,
                "currency": "MXN",
                "period": "monthly",
                "features": ["Búsquedas ilimitadas"]
            },
            {
                "name": "Plan Despacho",
                "price": 300,
                "currency": "MXN",
                "period": "monthly",
                "features": ["Búsquedas ilimitadas", "Soporte prioritario"]
            },
            {
                "name": "Plan Institucional",
                "price": 1000,
                "currency": "MXN",
                "period": "monthly",
                "features": ["Búsquedas ilimitadas", "Soporte prioritario", "API access"]
            }
        ]
    }

@app.post("/api/webhook/stripe")
async def stripe_webhook(request: Request):
    """Webhook para eventos de Stripe"""
    body = await request.body()
    return {"status": "received"}

# ===== ROOT =====
@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "Bienvenido a ValuaClick API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
