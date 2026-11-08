from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import settings

# Путь к бд(.env)
DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL) # Отвечает за физическое подключение и отправку запрсов в бд

AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    expire_on_commit=False, 
    class_=AsyncSession
)

# Базовый класс для всех моделей
class Base(DeclarativeBase):
    pass

# Генератор сессий для эндпоинтов 
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
