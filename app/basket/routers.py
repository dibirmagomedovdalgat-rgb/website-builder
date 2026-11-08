from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
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

    product_result = await db.execute(select(Product).where(Product.id == product_id)) # Запрос в бд что б найти товар по Id
    product = product_result.scalars().first() # Результат
    # Если товар с таким Id не найден
    if not product: 
        raise HTTPException(status_code=404, detail="Товар не найден") # Возвращается ошибка 404
    # Првоерка если товар уже в корзине
    basket_query = select(BasketItem).where(
        BasketItem.user_id == current_user.id, # Id пользователя  
        BasketItem.product_id == product_id # Id товара
    )
    basket_result = await db.execute(basket_query) # Запрос в бд
    existing_item = basket_result.scalars().first() # Первая найденная запись
    
    # Если товар уже лежит в корзине то он просто плюсуется 
    if existing_item:
        new_quantity = existing_item.quantity + quantity
        
        # Если количество 0 или меньше 0 удаляется товар из корзины
        if new_quantity <= 0:
            await db.delete(existing_item) # Удаление записи из сессии
            await db.commit() # Сохранение изменений
            return {"message": "Товар полностью удален из корзины"}
        
        # Иначе просто обновляется количество
        existing_item.quantity = new_quantity   
        await db.commit() # Сохранение изменений
        return {"message": f"Количество товара обновлено. Теперь в корзине: {existing_item.quantity}"}
    
    # Если товара в коризне не было
    if quantity <= 0:
        # Запрещается запись с нулевым и ниже нуля числом
        raise HTTPException(
            status_code=400, 
            detail="Нельзя добавить товар с нулевым или отрицательным количеством"
        )

    # Если товара нет в корзине и его число положительное то товар добавится 
    new_item = BasketItem(
        user_id=current_user.id, # Id пользователя 
        product_id=product_id, # Id продукта 
        quantity=quantity # Количесвто
    )
    db.add(new_item) # Добавление объекста в сессию бд
    await db.commit() # Сохранение в бд
    return {"message": "Товар успешно добавлен в корзину"}


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
