from typing import List, Optional
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import uuid
from datetime import datetime
from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Product(Base):
    __tablename__ = "products" # Имя таблицы товаров в бд

    id: Mapped[int] = mapped_column(primary_key=True, index=True) # Id товара 
    title: Mapped[str] = mapped_column(String(250), nullable=False) # Название товара
    description: Mapped[Optional[str]] = mapped_column(String(2000)) # Описание товара
    price: Mapped[int] = mapped_column(Integer, nullable=False) # Цена товара
    quantity: Mapped[int] = mapped_column(Integer, nullable=False) # Количество товара
    preview_image: Mapped[Optional[str]] = mapped_column(String(500), default=None) # Путь к главной фотке карточки товара
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=False) # Ключ на таблицу categories
    category: Mapped["Category"] = relationship(back_populates="products") # Ссылка на объект категории, типо: product.category.title
    images: Mapped[List["ProductImage"]] = relationship(
        back_populates="product", 
        cascade="all, delete-orphan"
    )

    def __str__(self):
        return self.title


class ProductImage(Base):
    __tablename__ = "product_images" # Имя таблицы доп. фотографий

    id: Mapped[int] = mapped_column(primary_key=True, index=True) # Id конкретной картинки в базе
    image_path: Mapped[str] = mapped_column(String(500), nullable=False) # Путь к файлу на сервере    
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True) # Id товара к которому привязана фотография
    product: Mapped["Product"] = relationship(back_populates="images") # Получить из фотографии данные объекта к которму она привязанна
    def __repr__(self) -> str:
        return self.image_path # Путь картинки

class Category(Base):
    __tablename__ = "categories" # Имя таблицы категории в бд

    id: Mapped[int] = mapped_column(primary_key=True, index=True) # Id категории
    title: Mapped[str] = mapped_column(String(250), nullable=False) # Название категории
    products: Mapped[List["Product"]] = relationship(back_populates="category", cascade="all, delete-orphan") # Ссылка на объект продукта, типо: category.products

    def __str__(self):
        return self.title


class TempUpload(Base):
    __tablename__ = "temp_uploads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)  # "preview" или "gallery"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
