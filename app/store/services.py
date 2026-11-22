from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from app.store.models import ShopSettings

# Возвращает настройки магазина из БД или создаёт запись по умолчанию.
async def get_or_create_shop_settings(db: AsyncSession) -> ShopSettings:
    result = await db.execute(select(ShopSettings).limit(1))
    shop = result.scalar_one_or_none()

    if not shop:
        shop = ShopSettings(
            name="Storefront",
            slogan="Качественные товары с удобной доставкой",
            about_text="Добро пожаловать в наш интернет-магазин! Мы предлагаем проверенные товары по честным ценам.",
            phone="+7 (999) 000-00-00",
            address="Самовывоз и доставка курьером",
            work_hours="Ежедневно с 09:00 до 21:00",
            social_link=None,
        )
        db.add(shop)
        await db.commit()
        await db.refresh(shop)

    return shop

# Возвращает настройки магазина из БД или объект по умолчанию.
async def get_shop_settings(db: AsyncSession) -> ShopSettings:
    try:
        result = await db.execute(select(ShopSettings).where(ShopSettings.id == 1))
        shop = result.scalar_one_or_none()
        if not shop:
            shop = ShopSettings(id=1)
            db.add(shop)
            await db.commit()
            await db.refresh(shop)
        return shop
    except (OperationalError, ProgrammingError):
        await db.rollback()
        return ShopSettings(id=1, name="Мой магазин")

