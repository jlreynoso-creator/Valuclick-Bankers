print("######## ESTE ES EL MAIN CORRECTO ########")
print("######## MAIN.PY CORRECTO ########")
from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional
import os
import stripe
import uvicorn

# =========================================================
# CONFIG
# =========================================================

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "CAMBIAR_EN_PRODUCCION_123456789"
)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

STRIPE_SECRET_KEY = os.getenv(
    "STRIPE_SECRET_KEY",
    ""
)

stripe.api_key = STRIPE_SECRET_KEY

# =========================================================
# FASTAPI
# =========================================================
app = FastAPI(
    title="ValuaClick API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# SECURITY
# =========================================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login"
)

# =========================================================
# FAKE DATABASE
# =========================================================

fake_users_db = {}

# =========================================================
# MODELS
# =========================================================

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

class SearchRequest(BaseModel):
    query: str
    location: Optional[str] = None

# =========================================================
# UTILS
# =========================================================

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(
        plain_password,
        hashed_password
    )

def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        days=ACCESS_TOKEN_EXPIRE_DAYS
    )

    to_encode.update({
        "exp": expire
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

def decode_token(token: str):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        email = payload.get("sub")

        if email is None:
            return None

        return email

    except JWTError:
        return None

# =========================================================
# ROOT
# =========================================================

@app.get("/")
async def root():
    return {
        "message": "ValuaClick API funcionando",
        "status": "ok",
        "docs": "/docs"
    }

# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
async def health():
    return {
        "status": "healthy"
    }

# =========================================================
# REGISTER
# =========================================================

@app.post("/api/auth/register")
async def register(user: UserRegister):

    if user.email in fake_users_db:
        raise HTTPException(
            status_code=400,
            detail="El usuario ya existe"
        )

    hashed_password = hash_password(
        user.password
    )

    fake_users_db[user.email] = {
        "email": user.email,
        "name": user.name,
        "password": hashed_password
    }

    return {
        "message": "Usuario registrado correctamente"
    }

# =========================================================
# LOGIN
# =========================================================

@app.post(
    "/api/auth/login",
    response_model=TokenResponse
)
async def login(user: UserLogin):

    db_user = fake_users_db.get(
        user.email
    )

    if not db_user:
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas"
        )

    valid_password = verify_password(
        user.password,
        db_user["password"]
    )

    if not valid_password:
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas"
        )

    access_token = create_access_token({
        "sub": user.email
    })

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

# =========================================================
# CURRENT USER
# =========================================================

@app.get("/api/user/me")
async def get_current_user(
    token: str = Depends(oauth2_scheme)
):

    email = decode_token(token)

    if not email:
        raise HTTPException(
            status_code=401,
            detail="Token inválido"
        )

    user = fake_users_db.get(email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado"
        )

    return {
        "email": user["email"],
        "name": user["name"],
        "subscription_plan": "free"
    }

# =========================================================
# SEARCH
# =========================================================

@app.post("/api/search")
async def search(
    request: SearchRequest
):
    return {
        "results": [],
        "query": request.query,
        "location": request.location,
        "message": "Búsqueda realizada correctamente"
    }

# =========================================================
# PRICING
# =========================================================

@app.get("/api/pricing")
async def pricing():

    return {
        "plans": [
            {
                "name": "Agente",
                "price": 150,
                "currency": "MXN"
            },
            {
                "name": "Despacho",
                "price": 300,
                "currency": "MXN"
            },
            {
                "name": "Institucional",
                "price": 1000,
                "currency": "MXN"
            }
        ]
    }

# =========================================================
# STRIPE CHECKOUT
# =========================================================

@app.post("/api/subscription/checkout")
async def checkout(plan: str):

    return {
        "message": "Stripe configurado",
        "plan": plan
    }

# =========================================================
# STRIPE WEBHOOK
# =========================================================

@app.post("/api/webhook/stripe")
async def stripe_webhook(
    request: Request
):

    payload = await request.body()

    return {
        "received": True
    }

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )
