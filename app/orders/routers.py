from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.users.auth import get_current_user
from app.users.models import User
from app.orders.models import Order, OrderItem, OrderStatus
from app.orders.schemas import OrderCreate, OrderFullResponse, OrderShortResponse
from app.basket.models import BasketItem 
from app.products.models import Product
from app.orders.services import process_order_cancellation

# Это типо путь: /orders автоматически ставится везде.Если к примеру @router.post("/4") то будет /orders/4
router = APIRouter(prefix="/orders", tags=["Заказы"])


@router.post("", response_model=OrderFullResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate, # JSON с фронтенда
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) # Проверка JWT токена
):
    # Данные пользователя
    user_id = current_user.id # Id
    user_name = current_user.name # Имя
    user_phone = order_data.phone or current_user.phone # Если номера телефона нет в JSON ен возьмется с бд
    user_email = current_user.email # Email

    basket_query = (
        select(BasketItem) # Записи из модели BasketItem
        .where(BasketItem.user_id == user_id)
        .options(selectinload(BasketItem.product))
        .order_by(BasketItem.product_id)
    )
    basket_result = await db.execute(basket_query) # Отправка запроса в бд
    basket_items = basket_result.scalars().all() # Результат

    # Если корзина пуста
    if not basket_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, # Код ошибки
            detail="Невозможно оформить заказ: ваша корзина пуста" # Сообщение 
        )

     # Если нет номера телефона
    if not user_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите номер телефона для оформления заказа."
        )

    # Если в заказе указали номер а в профиле его нет то он автоматически запишется в профиле
    if not current_user.phone and order_data.phone:
        # Проверка не занят ли номер телефона
        existing_user = await db.execute(
            select(User).where(User.phone == order_data.phone, User.id != user_id)
        )
        if not existing_user.scalar_one_or_none():
            current_user.phone = order_data.phone

    # Проверка наличия и подсчет общей стоимости заказа
    total_price = 0
    for item in basket_items: # Цикл в корзине
        if not item.product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Один из товаров в корзине больше не существует"
            )
        if item.product.quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно товара '{item.product.title}' на складе. Доступно: {item.product.quantity} шт."
            )
        total_price += item.product.price * item.quantity  # Умножение цены товара на его количество и прибавление к счетчику 

    # Создание заказа, данные берутся из переменных
    new_order = Order(
        user_id=user_id, # Id пользователя
        status=OrderStatus.NEW, # Статус заказа
        user_name=user_name, # Имя
        user_phone=user_phone, # Номер телефона
        user_email=user_email, # Email
        total_price=total_price, # Итоговая сумма
        delivery_address=order_data.delivery_address, # Адрес доставки (По дефолту самовывоз)
        comment=order_data.comment # Комментарий к заказу
    )
    
    db.add(new_order)
    await db.flush()  # Пока что запись в черновике

    # Запуск цикла по всем элементам, которые вытащили из корзины пользователя
    for item in basket_items:
        # Атомарное списание со склада
        stock_update = (
            update(Product)
            .where(
                Product.id == item.product_id,
                Product.quantity >= item.quantity,
            )
            .values(quantity=Product.quantity - item.quantity)
            .returning(Product.id)
        )
        stock_result = await db.execute(stock_update)
        updated_product_id = stock_result.scalar_one_or_none()

        # Если другой заказ
        if updated_product_id is None:
            await db.rollback()  # Откат
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно товара '{item.product.title}' на складе (товар купили быстрее вас)."
            )

        order_item = OrderItem(
            order_id=new_order.id,  # Id заказа
            product_id=item.product_id,  # Id продукта
            product_name=item.product.title,  # Название
            price=item.product.price,  # Фиксация цены на момент покупки
            quantity=item.quantity  # Количество
        )
        db.add(order_item)

    # Очистка корзины пользователя в бд по его Id
    delete_basket_query = delete(BasketItem).where(BasketItem.user_id == user_id) 
    await db.execute(delete_basket_query)
    
    created_order_id = new_order.id  # Запись Id пока объект не сбросился
    await db.commit()  # Сохранение всей транзакции целиком
    
    # Загрузка созданных items для корректного ответа схемы OrderFullResponse
    order_full_query = (
        select(Order)
        .where(Order.id == created_order_id)  # То самое число которое сохранилось перед сбросом
        .options(selectinload(Order.items))
    )
    order_full_query_result = await db.execute(order_full_query)  # Запрос бд
    order_to_return = order_full_query_result.scalar_one()  # Результат

    return order_to_return

# Отмена заказа
@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: int, # Id заказа 
    current_user: User = Depends(
        get_current_user
    ),
    session: AsyncSession = Depends(get_db)
):
    # Вызов функции для отмены
    updated_order = await process_order_cancellation(order_id, session, current_user)
    # Сохранение изменений в бд
    await session.commit()
    return {
        "status": "success", 
        "message": f"Заказ №{updated_order.id} отменен, товары возвращены на склад."
    }
