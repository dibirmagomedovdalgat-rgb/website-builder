from typing import Optional
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class ShopSettings(Base):
    __tablename__ = "shop_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(150), default="Мой магазин", nullable=False)
    slogan: Mapped[Optional[str]] = mapped_column(String(255), default="Качественные товары с доставкой")
    about_text: Mapped[Optional[str]] = mapped_column(Text, default=None)
    phone: Mapped[Optional[str]] = mapped_column(String(50), default=None)
    address: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    work_hours: Mapped[Optional[str]] = mapped_column(String(150), default=None)
    social_link: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    theme_css: Mapped[str] = mapped_column(String(150), default="default.css", nullable=False)
