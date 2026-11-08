from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.users.models import User
from app.products.models import Product


class BasketItem(Base):
    __tablename__ = "basket_items" # Имя таблицы товаров в бд

    id: Mapped[int] = mapped_column(primary_key=True, index=True) #Id
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False) # Привязка строки корзины
    
    # Привязка строки корзины к продукту
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), 
        nullable=False
    )
    # Количество этого товара в корзине
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Настройка связей
    user: Mapped["User"] = relationship(back_populates="basket_items")
    product: Mapped["Product"] = relationship()

    def __str__(self) -> str:
         return f"Id товара - {self.product_id} количество - x{self.quantity}" # Id товара и его количество

