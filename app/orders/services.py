from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.orders.models import Order, OrderItem, OrderStatus
from app.products.models import Product
from app.users.models import User

# Отмена заказа
async def process_order_cancellation(order_id: int, session: AsyncSession, current_user: User,):
    # Загрузка заказа из бд
    result = await session.execute(select(Order).where(Order.id == order_id)) # Запрос в бд
    order = result.scalar_one_or_none() # Результат
    
    if not order: # Если по запросу ничего не нашлось
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверка что заказ отменяет его владелец или админ
    if order.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не можете отменить чужой заказ",
        )
        
    # Если заказ  уже отменен
    if order.status == OrderStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Заказ уже отменен"
        )
    
    # Если заказ уже выполнен
    if order.status == OrderStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Выполненный заказ нельзя отменить"
        )

    # Загрузка товаров из заказа
    items_result = await session.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    items = items_result.scalars().all()
    
    # Возвращение товара на склад
    for item in items:
        if item.product_id:
            await session.execute(
                update(Product)
                .where(Product.id == item.product_id)
                .values(quantity=Product.quantity + item.quantity)
            )
            
    # Смены статуса на ОТМЕНЕН
    order.status = OrderStatus.CANCELLED
    return order