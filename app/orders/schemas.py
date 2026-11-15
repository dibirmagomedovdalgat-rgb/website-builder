from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.orders.models import OrderStatus

# Информация об одном товаре
class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int 
    product_id: Optional[int]
    product_name: str
    price: int = Field(..., description="Цена на момент покупки")
    quantity: int


# Все товары достанутся из корзины автоматически по user_id в бд.
class OrderCreate(BaseModel):
    phone: Optional[str] = Field(default=None, max_length=30)
    delivery_address: Optional[str] = Field(default="Самовывоз", max_length=500)
    comment: Optional[str] = Field(None, max_length=1000)

    # Убирает лишние пробелы
    @field_validator("phone", mode="before")
    @classmethod
    def clean_phone(cls, value: Optional[str]) -> Optional[str]:
        if isinstance(value, str):
            value = value.strip()
            return value if value else None
        return value


# Краткая информация о заказе
class OrderShortResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: OrderStatus
    total_price: int
    created_at: datetime


# Полная информация о заказе со всеми вложенными товарами
class OrderFullResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: Optional[int]
    status: OrderStatus
    user_name: Optional[str]
    user_phone: Optional[str]
    user_email: Optional[str]
    total_price: int
    delivery_address: str
    comment: Optional[str]
    created_at: datetime
    items: List[OrderItemResponse]  # Список товаров взятых из корзины
