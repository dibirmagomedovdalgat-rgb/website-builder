from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.users.auth import get_current_user
from app.users.models import User
from app.orders.models import Order, OrderItem, OrderStatus
from app.orders.schemas import OrderCreate, OrderFullResponse, OrderShortResponse
from app.basket.models import BasketItem 

# Это типо путь: /orders автоматически ставится везде.Если к примеру @router.post("/4") то будет /orders/4
router = APIRouter(prefix="/orders", tags=["Заказы"])


@router.post("", response_model=OrderFullResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    order_data: OrderCreate, # JSON с фронтенда
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) # Проверка JWT токена
):
    basket_query = (
        select(BasketItem) # Записи из модели BasketItem
        .where(BasketItem.user_id == current_user.id) # Только те, которые принадлежат текущему пользователю
        .options(selectinload(BasketItem.product))
    )
    basket_result = await db.execute(basket_query) # Отправка запроса в бд
    basket_items = basket_result.scalars().all() # Результат

    # Если корзина пуста
    if not basket_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, # Код ошибки
            detail="Невозможно оформить заказ: ваша корзина пуста" # Сообщение 
        )

    # Проверка достаточно ли товара
    for item in basket_items:
        if item.product.quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно товара '{item.product.title}' на складе. Доступно: {item.product.quantity} шт."
            )

    # Общая стоимость заказа
    total_price = 0
    for item in basket_items: # Цикл в корзине
        total_price += item.product.price * item.quantity # Умножение цены товара на его количество и прибавление к счетчику 

    # Создание заказа, данные пользователя заполняются по его профилю
    new_order = Order(
        user_id=current_user.id,        # Id юзера 
        status=OrderStatus.NEW,         # Статус
        user_name=current_user.name,    # Имя
        user_phone=current_user.phone,  # Номер телефона
        user_email=current_user.email,  # Email
        total_price=total_price,        # Итоговая сумма
        delivery_address=order_data.delivery_address, # Адрес доставки (По дефолту самовывоз)
        comment=order_data.comment # Комментарий к заказу
    )
    
    db.add(new_order)
    await db.flush()  # Пока что запись в черновике

    # Запуск цикла по всем элементам, которые вытащили из корзины пользователя
    for item in basket_items:
        order_item = OrderItem(
            order_id=new_order.id, # Id заказа
            product_id=item.product_id, # Id продукта
            product_name=item.product.title, # Название
            price=item.product.price, # Фиксируем цену (int) на момент покупки
            quantity=item.quantity  # Количество
        )
        db.add(order_item)
        
        # Убавляем колличество товара так как его заказали
        item.product.quantity -= item.quantity

    delete_basket_query = delete(BasketItem).where(BasketItem.user_id == current_user.id) # Очистка корзины пользователя в бд
    await db.execute(delete_basket_query)
    await db.commit() # Сохранение
    
    # Загрузка созданных items для корректного ответа схемы OrderFullResponse
    order_full_query = (
        select(Order)
        .where(Order.id == new_order.id) # Только что созданный заказ по Id
        .options(selectinload(Order.items))
    )
    order_full_result = await db.execute(order_full_query) # Запрос бд
    order_to_return = order_full_result.scalar_one() # Результат

    return order_to_return


# Получение истории заказов с краткой инфой
@router.get("", response_model=list[OrderShortResponse])
async def get_my_orders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) # Какой именно пользователь делает запрос
):
    # Добавлен .order_by() для сортировки, если у вас в модели есть поле серийного времени (например, created_at)
    query = select(Order).where(Order.user_id == current_user.id)
    if hasattr(Order, 'created_at'):
        query = query.order_by(Order.created_at.desc())
        
    result = await db.execute(query) # Запрос бд
    return result.scalars().all()


# Получение деталей одного заказа с полной инфой
@router.get("/{order_id}", response_model=OrderFullResponse)
async def get_order_details(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) # Какой именно пользователь делает запрос
):
    query = (
        select(Order)
        .where(Order.id == order_id, Order.user_id == current_user.id) # Поиск заказа по его Id и проверка, что он принадлежит именно ему
        .options(selectinload(Order.items))
    )
    result = await db.execute(query) # Запрос в бд
    order = result.scalar_one_or_none() # Вернет объект order, а если что-то пошло не так — то None

    # Если order это None 
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, # Ошибка
            detail="Заказ не найден" # Текст ошибки
        )
    return order
