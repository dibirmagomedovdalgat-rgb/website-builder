from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.database import get_db
from app.users.auth import get_current_user
from app.users.models import User
from app.products.models import Product
from app.basket.models import BasketItem

router = APIRouter(prefix="/basket", tags=["Корзина"])

# Добавляет товар в корзину
@router.post("/add")
async def add_item_to_basket(
    product_id: int, 
    quantity: int = 1,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Есди количество меньше нуля
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Количество для добавления должно быть больше 0."
        )

    # Поиск товара в бд
    product_result = await db.execute(select(Product).where(Product.id == product_id))
    product = product_result.scalars().first()
    if not product: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")

    # Проверка, есть ли товар уже в корзине пользователя
    basket_query = select(BasketItem).where(
        BasketItem.user_id == current_user.id,  
        BasketItem.product_id == product_id
    )
    basket_result = await db.execute(basket_query)
    existing_item = basket_result.scalars().first()
    
    # Если товар уже был в корзине то он просто суммируется 
    if existing_item:
        new_quantity = existing_item.quantity + quantity
        
        if new_quantity > product.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Недостаточно товара на складе. Доступно: {product.quantity} шт. (в корзине уже: {existing_item.quantity} шт.)"
            )

        existing_item.quantity = new_quantity   
        await db.commit()
        return {"message": f"Количество товара обновлено. Теперь в корзине: {existing_item.quantity}"}
    
    # Если товара еще нет в корзине
    if quantity > product.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недостаточно товара на складе. Доступно: {product.quantity} шт."
        )
    
    # Если товара нет в корзине и его число положительное то товар добавится 
    new_item = BasketItem(
        user_id=current_user.id, 
        product_id=product_id, 
        quantity=quantity
    )
    db.add(new_item) # Добавление объекста в сессию бд
    try:
        await db.commit() # Сохранение в бд
        return {"message": "Товар успешно добавлен в корзину"}
    # Если параллельный запрос успел создать эту запись раньше
    except IntegrityError:
        await db.rollback() # Откат ошибки в сессии
        
        retry_result = await db.execute(basket_query) # Повторный поиск записи в бд
        existing_item = retry_result.scalars().first() # Первая найденная запись
        if existing_item:
            new_quantity = existing_item.quantity + quantity
            # Если новое количество превышает остаток на скаде
            if new_quantity > product.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Недостаточно товара на складе. Доступно: {product.quantity} шт. (в корзине уже: {existing_item.quantity} шт.)"
                )
            existing_item.quantity = new_quantity # Обновление количества
            await db.commit() # Сохранение изменений
            return {"message": f"Количество товара обновлено. Теперь в корзине: {existing_item.quantity}"}

@router.post("/decrease")
async def decrease_item_in_basket(
    product_id: int, 
    quantity: int = 1,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Количество для уменьшения должно быть больше 0"
        )

    # Поиск товара в корзине
    basket_query = select(BasketItem).where(
        BasketItem.user_id == current_user.id,
        BasketItem.product_id == product_id
    )
    basket_result = await db.execute(basket_query)
    existing_item = basket_result.scalars().first()

    # Если товара нет
    if not existing_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Товар не найден в корзине"
        )

    new_quantity = existing_item.quantity - quantity

    # Если после уменьшение количество товара ноль или меньше то он удаляется с корзины
    if new_quantity <= 0:
        await db.delete(existing_item)
        await db.commit()
        return {"message": "Товар полностью удален из корзины"}

    existing_item.quantity = new_quantity
    await db.commit()
    return {"message": f"Количество товара уменьшено. Теперь в корзине: {existing_item.quantity}"}

# Достать всю корзину и посчитать всю сумму товаров в ней
@router.get("/me")
async def get_my_basket(
    current_user: User = Depends(get_current_user), # Id пользователя 
    db: AsyncSession = Depends(get_db) # Сессия бд
):
    # Зарпрос в бд для поска товаров в коризе юзера
    query = select(BasketItem).where(BasketItem.user_id == current_user.id).options(joinedload(BasketItem.product)) # joinedload(BasketItem.product) сразу достает информацию о продукте
    result = await db.execute(query) # Запрос в бд
    items = result.scalars().all()  # Результат

    total_price = 0  # Итоговая сумма корзины
    basket_list = []
    
    for item in items: # Перебор циклом каждого товара
        item_total = item.product.price * item.quantity  # Подсчест стоимости учитывая количество товара
        total_price += item_total # Добавление результата в общую стоимость корзины
        
        basket_list.append({
            "basket_item_id": item.id,  # Id записи в коризне
            "product_name": item.product.title,  # Название продукта
            "price_per_item": item.product.price,  # Цена за 1 штуку
            "quantity": item.quantity, # Количество
            "item_total_price": item_total # Общая стоимость
        })

    return {
        "user_email": current_user.email, # Почта юзера
        "items": basket_list, # Список товаров
        "total_basket_price": total_price # Финальная цена
    }
