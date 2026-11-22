from contextlib import asynccontextmanager
from pathlib import Path
import asyncio
import bcrypt
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.admin.routers import router as admin_router
from app.basket.models import BasketItem
from app.basket.routers import router as basket_router
from app.database import Base, engine
from app.orders.models import Order, OrderItem
from app.orders.routers import router as order_router
from app.products.models import Product, ProductImage, TempUpload
from app.products.routers import router as product_router
from app.products.services import BASE_DIR
from app.store.models import ShopSettings
from app.store.routers import router as store_router
from app.users.models import User
from app.users.routers import router as user_router
from config import settings

# Создает админа при первом запуске если его нет
async def create_default_admin() -> None:
    async with AsyncSession(engine) as session:
        result = await session.execute(select(User).where(User.role == "admin").limit(1))
        existing_admin = result.scalar_one_or_none()
        if existing_admin:
            return

        hashed = bcrypt.hashpw(b"admin12345", bcrypt.gensalt()).decode("utf-8")
        default_admin = User(
            name="Admin",
            email="admin@myshop.com",
            hashed_password=hashed,
            role="admin",
            is_active=True,
        )
        session.add(default_admin)
        await session.commit()


# Создание таблиц и дефолтного администратора при старте с ожиданием готовности бд
@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(10):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            break
        except Exception:
            if attempt == 9:
                raise
            await asyncio.sleep(2)

    await create_default_admin()
    yield



app = FastAPI(lifespan=lifespan)

# Все роуты
app.include_router(user_router)
app.include_router(product_router)
app.include_router(basket_router)
app.include_router(order_router)
app.include_router(admin_router)
app.include_router(store_router)

# Статические файлы и изображения
APP_DIR = Path(__file__).resolve().parent
ROOT_DIR = APP_DIR.parent

STORE_STATIC_DIR = APP_DIR / "store" / "static"
STORE_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STORE_STATIC_DIR)), name="store_static")

ADMIN_STATIC_DIR = APP_DIR / "admin" / "static"
ADMIN_STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/admin/static", StaticFiles(directory=str(ADMIN_STATIC_DIR)), name="admin_static")

IMG_DIR = ROOT_DIR / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/img", StaticFiles(directory=str(IMG_DIR)), name="img")


# Редирект с главной страницы на витрину магазина
@app.get("/")
def read_root():
    return RedirectResponse(url="/", status_code=302)
