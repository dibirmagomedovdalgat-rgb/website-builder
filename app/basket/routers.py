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

    # Проверка существует ли товар
    product_result = await db.execute(select(Product).where(Product.id == product_id))
    if not product_result.scalars().first():
        raise HTTPException(status_code=404, detail="Товар не найден")

    # Проверка есть ли этот товар уже в корзине
    basket_query = select(BasketItem).where(
        BasketItem.user_id == current_user.id,
        BasketItem.product_id == product_id
    )
    basket_result = await db.execute(basket_query)
    existing_item = basket_result.scalars().first()
    
    # Если товар уже в корзине то он просто плюсуется к существующему
    if existing_item:
        new_quantity = existing_item.quantity + quantity
        
        # Если колличество 0 или оно ушло в минус, удаляется товар
        if new_quantity <= 0:
            await db.delete(existing_item)
            await db.commit()
            return {"message": "Товар полностью удален из корзины"}
        
        # Иначе просто обновляется колличество
        existing_item.quantity = new_quantity
        await db.commit()
        return {"message": f"Количество товара обновлено. Теперь в корзине: {existing_item.quantity}"}
    
    if quantity <= 0:
        raise HTTPException(
            status_code=400, 
            detail="Нельзя добавить товар с нулевым или отрицательным количеством"
        )

    # Если товара нет добавляется 
    new_item = BasketItem(
        user_id=current_user.id,
        product_id=product_id,
        quantity=quantity
    )
    db.add(new_item)
    await db.commit()
    return {"message": "Товар успешно добавлен в корзину"}


# Достать всю корзину и посчитать всю сумму товаров в ней
@router.get("/me")
async def get_my_basket(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(BasketItem).where(BasketItem.user_id == current_user.id).options(joinedload(BasketItem.product))
    result = await db.execute(query)
    items = result.scalars().all()

    total_price = 0
    basket_list = []
    
    for item in items:
        item_total = item.product.price * item.quantity
        total_price += item_total
        
        basket_list.append({
            "basket_item_id": item.id,
            "product_name": item.product.name,
            "price_per_item": item.product.price,
            "quantity": item.quantity,
            "item_total_price": item_total
        })

    return {
        "user_email": current_user.email,
        "items": basket_list,
        "total_basket_price": total_price
    }
