from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, Enum
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta
import enum

Base = declarative_base()

class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    AGENTE = "agente"
    DESPACHO = "despacho"
    INSTITUCIONAL = "institucional"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)  # Null si usa OAuth
    
    # OAuth
    google_id = Column(String, unique=True, nullable=True)
    oauth_provider = Column(String, nullable=True)  # 'google', 'email'
    
    # Suscripción
    subscription_plan = Column(String, default=SubscriptionPlan.FREE)
    subscription_id = Column(String, nullable=True)  # Stripe subscription ID
    subscription_expires = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Búsquedas
    search_count = Column(Integer, default=0)
    last_search_date = Column(DateTime, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def is_subscription_active(self):
        """Verifica si la suscripción está activa"""
        if self.subscription_plan == SubscriptionPlan.FREE:
            return False
        if self.subscription_expires is None:
            return False
        return datetime.utcnow() < self.subscription_expires
    
    def remaining_free_searches(self):
        """Retorna búsquedas gratuitas restantes"""
        if self.subscription_plan != SubscriptionPlan.FREE:
            return float('inf')
        return max(0, 2 - self.search_count)
    
    def can_search(self):
        """Determina si puede hacer búsquedas"""
        if self.subscription_plan == SubscriptionPlan.FREE:
            return self.search_count < 2
        return self.is_subscription_active()


class SearchLog(Base):
    __tablename__ = "search_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=True)  # Null si es anónimo
    session_id = Column(String, index=True, nullable=True)  # Para anónimos
    
    query = Column(String, nullable=False)
    portales_searched = Column(Text, nullable=True)  # JSON de portales usados
    result_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class StripeEvent(Base):
    __tablename__ = "stripe_events"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True)
    event_type = Column(String)
    user_id = Column(Integer, nullable=True)
    
    data = Column(Text)  # JSON full event
    processed = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
