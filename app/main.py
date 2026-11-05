from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import engine, Base
from sqladmin import Admin

from app.users.routers import router as user_router
from app.products.routers import router as product_router
from app.basket.routers import router as basket_router
from app.orders.routers import router as order_router
from app.admin import ProductAdmin, ProductImageAdmin 
from app.admin_auth import authentication_backend
from app.admin import ProductAdmin, ProductImageAdmin, BasketItemAdmin,OrderAdmin, OrderItemAdmin,UserAdmin
from config import settings  
from app.basket.models import BasketItem
from app.users.models import User
from app.products.models import Product, ProductImage
from app.orders.models import Order, OrderItem

# Cоздание таблиц при старте
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(user_router)
app.include_router(product_router) 
app.include_router(basket_router)
app.include_router(order_router)


admin = Admin(
    app=app, 
    engine=engine, 
    title="Панель управления",
    authentication_backend=authentication_backend
)

admin.add_view(ProductAdmin)
admin.add_view(ProductImageAdmin)
admin.add_view(BasketItemAdmin)
admin.add_view(OrderAdmin)
admin.add_view(OrderItemAdmin)
admin.add_view(UserAdmin)

@app.get("/")
def read_root():
    return {
        "message": "FastApi работает",
        "database_status": "Бд работает"
    }
