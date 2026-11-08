import enum
from datetime import datetime
from typing import List, Optional
from sqlalchemy import ForeignKey, String, DateTime, Integer, Enum, func, event, inspect, select, update
from sqlalchemy import update, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session
from app.database import Base
from app.products.models import Product



# Список статусов заказа
class OrderStatus(enum.Enum):
    NEW = "new"                 # Новый
    PROCESSING = "processing"   # В работе
    COMPLETED = "completed"     # Выполнен
    CANCELLED = "cancelled"     # Отменен


# Модель заказа
class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True, index=True) # Id заказа
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=False) # Id пользователя  
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.NEW,nullable=False) # Статус заказа Новый/В работе/Выполнен/Отменен. По дефолту новый
    user_name: Mapped[str] = mapped_column(String(100), nullable=False) # Имя пользователя берется автоматичски из профиля
    user_phone: Mapped[str] = mapped_column(String(20), nullable=False) # Номер телефона пользователя берется автоматичски из профиля
    user_email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True) # Email пользвателя берется автоматичски из профиля
    total_price: Mapped[int] = mapped_column(Integer, nullable=False) # Итоговая сумма заказа
    delivery_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, default="Самовывоз") # Адрес доставки, если не указали то будет Самовывоз
    comment: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True) # Комментарий к заказу
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now()) # Дата зодания заказа
    items: Mapped[List["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan") # Автоматически связывает заказ с его товарами и удаляет товары, если заказ удалён

    def __str__(self) -> str:
        return f"Id - {self.id} Имя - {self.user_name}" # Id заказа и имя


# Модель хранит точные цены и названия товаров на момент покупки, чтобы они не изменились при обновлении каталога
class OrderItem(Base):
    __tablename__ = "order_items" # Название таблицы
    id: Mapped[int] = mapped_column(primary_key=True, index=True)  # Id товара
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)  # Id заказа
    product_id: Mapped[Optional[int]] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), nullable=True) # Связывает позицию в чеке с текущим товаром на витрине
    # Срез данных товара на момент покупки (чтобы не сломалось при изменении каталога)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False) # Название продукта
    price: Mapped[int] = mapped_column(Integer, nullable=False)  # Цена продукта
    quantity: Mapped[int] = mapped_column(nullable=False) # Количество продукта
    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()

    def __str__(self) -> str:
        return f"{self.product_name} (x{self.quantity})" # Название продукта и его количесво