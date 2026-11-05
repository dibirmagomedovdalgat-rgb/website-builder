from sqladmin import ModelView
from app.products.models import Product, ProductImage
from app.basket.models import BasketItem
from app.orders.models import Order, OrderItem # Добавили импорт моделей заказов
from app.users.models import User


# Как товар будет выглядеть в админке
class ProductAdmin(ModelView, model=Product):
    column_list = [Product.id, Product.title, Product.price, Product.preview_image] # Колонки в таблице списка
    column_searchable_list = [Product.title, Product.description] # Поля по которым работает поиск
    column_sortable_list = [Product.id, Product.price] # Поля по которым можно сортировать
    icon = "fa-solid fa-tag" # Иконка
    name = "Товар"
    name_plural = "Товары"


# Как дополнительные картинки будут выглядеть в админке
class ProductImageAdmin(ModelView, model=ProductImage):
    column_list = [ProductImage.id, ProductImage.product_id, ProductImage.image_path]
    icon = "fa-solid fa-image" # Иконка
    name = "Доп. фото"
    name_plural = "Доп. фотографии"


# Как корзина будет выглядеть в админке
class BasketItemAdmin(ModelView, model=BasketItem):
    column_list = [BasketItem.id, "user.email", "product.title", BasketItem.quantity]
    icon = "fa-solid fa-basket-shopping" # Иконка
    name = "Товар в корзине"
    name_plural = "Корзины пользователей"


# Как заказы пользователей будут выглядеть в админке
from sqlalchemy import select
from sqladmin import ModelView
from app.orders.models import Order
from app.users.models import User 

# Импортируем фабрику сессий напрямую из вашего файла конфигурации БД
from app.database import AsyncSessionLocal 

class OrderAdmin(ModelView, model=Order):
    column_list = [Order.id, Order.status, Order.total_price, Order.user_name, Order.user_phone, Order.created_at]
    column_searchable_list = [Order.id, Order.user_name, Order.user_phone, Order.user_email]
    column_filters = [Order.status, Order.created_at] 
    
    form_columns = [
        "status",           
        "user_name",        
        "user_phone",       
        "user_email",       
        "total_price",      
        "delivery_address", 
        "comment"           
    ]
    
    async def on_model_change(self, data: dict, model: Order, is_created: bool, request) -> None:
        if is_created:
            # Открываем независимую сессию для безопасного поиска админа
            async with AsyncSessionLocal() as local_session:
                result = await local_session.execute(select(User).limit(1))
                admin_user = result.scalar_one_or_none()
                
                if admin_user:
                    # Привязываем заказ к найденному администратору
                    model.user_id = admin_user.id
                    
                    # Подставляем текстовые данные профиля, если они не были заполнены руками в форме
                    if not data.get("user_name"):
                        model.user_name = admin_user.name
                    if not data.get("user_email"):
                        model.user_email = admin_user.email
                    if not data.get("user_phone"):
                        model.user_phone = admin_user.phone
    
    column_default_sort = ("created_at", True) 
    icon = "fa-solid fa-truck-ramp-box" 
    name = "Заказ"
    name_plural = "Заказы"


# Описание позиции чека внутри заказов
class OrderItemAdmin(ModelView, model=OrderItem):
    column_list = [OrderItem.id, OrderItem.order_id, OrderItem.product_name, OrderItem.price, OrderItem.quantity]
    column_searchable_list = [OrderItem.product_name]
    form_columns = [OrderItem.product_name, OrderItem.price, OrderItem.quantity]
    icon = "fa-solid fa-receipt" # Иконка чека
    name = "Позиция заказа"
    name_plural = "Позиции заказов"

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.name, User.email, User.is_active, User.role]
    column_searchable_list = [User.name, User.email]
    can_create = False  
    form_excluded_columns = [User.hashed_password] 
    column_details_exclude_list = [User.hashed_password]
    icon = "fa-solid fa-users"  
    name = "Пользователь"
    name_plural = "Пользователи"