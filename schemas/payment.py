from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class PaymentCreate(BaseModel):
    amount: float
    description: str


class PaymentResponse(BaseModel):
    id: str
    status: str
    confirmation_url: str
    operation_id: int
    amount: str
    currency: str


class PaymentStatusResponse(BaseModel):
    id: str
    status: str
    paid: bool
    amount: str
    currency: str
    description: str
    metadata: dict


class SubscriptionStatusResponse(BaseModel):
    is_verified: bool
    is_active: bool
    subscription_exp: Optional[datetime]
    days_remaining: int


class WebhookResponse(BaseModel):
    status: str