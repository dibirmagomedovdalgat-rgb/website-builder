from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.database import Base
from typing import List
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users" # Имя таблицы в бд
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True) # Id
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False) # EMAIL
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False) # Хэш пароля
    bio: Mapped[str | None] = mapped_column(String(1000), default=None) # Описание профиля/О себе
    phone: Mapped[str | None] = mapped_column(String(30), unique=True, index=True, default=None, nullable=True) 
    image_path: Mapped[str | None] = mapped_column(default=None) # Путь к аватарке
    is_active: Mapped[bool] = mapped_column(default=True) # Статус доступа к аккаунту: True - активен, False - забанен/отключен
    role: Mapped[str] = mapped_column(String(20), default="user")# Роль пользователя(user, staff, admin), по дефолту user
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now()) # Дата регистраци
    basket_items: Mapped[List["BasketItem"]] = relationship(
        "BasketItem", 
        back_populates="user", 
        cascade="all, delete-orphan"
    )

    def __str__(self) -> str:
        return self.name