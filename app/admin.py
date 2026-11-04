from sqladmin import ModelView
from app.products.models import Product, ProductImage
from app.basket.models import BasketItem
from app.orders.models import Order, OrderItem # Добавили импорт моделей заказов


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
class OrderAdmin(ModelView, model=Order):
    column_list = [Order.id, Order.status, Order.total_price, Order.user_name, Order.user_phone, Order.created_at]
    column_searchable_list = [Order.id, Order.user_name, Order.user_phone, Order.user_email]
    column_filters = [Order.status, Order.created_at] # Фильтры по статусу заказа и дате оформления
    form_columns = [Order.status, Order.delivery_address, Order.comment]
    column_default_sort = ("created_at", True) # Свежие заказы всегда будут вверху списка
    icon = "fa-solid fa-truck-ramp-box" # Иконка
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
