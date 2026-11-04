from typing import List, Optional
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Product(Base):
    __tablename__ = "products" # Имя таблицы товаров в базе

    id: Mapped[int] = mapped_column(primary_key=True, index=True) # Id товара 
    title: Mapped[str] = mapped_column(String(250), nullable=False) # Название товара
    description: Mapped[Optional[str]] = mapped_column(String(2000)) # Описание товара
    price: Mapped[int] = mapped_column(Integer, nullable=False) # Цена товара
    quantity: Mapped[int] = mapped_column(Integer, nullable=False) # Колличество товара
    preview_image: Mapped[Optional[str]] = mapped_column(String(500), default=None) # Путь к главной фотке карточки товара
    images: Mapped[List["ProductImage"]] = relationship(
        back_populates="product", 
        cascade="all, delete-orphan"
    )


class ProductImage(Base):
    __tablename__ = "product_images" # Имя таблицы доп. фотографий

    id: Mapped[int] = mapped_column(primary_key=True, index=True) # Id конкретной картинки в базе
    image_path: Mapped[str] = mapped_column(String(500), nullable=False) # Путь к файлу на сервере    
    # Id товара к которому привязана фотография
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), 
        index=True
    )
    product: Mapped["Product"] = relationship(back_populates="images") # Получить из фотографии данные объекта к которму она привязанна
