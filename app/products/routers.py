from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db  
from app.products.models import Product, ProductImage
from app.products.schemas import ProductResponse, ProductShortResponse, ProductCreate


# Это типо путь: /products автоматически ставится везде.Если к примеру @router.post("/register") то будет products/register
router = APIRouter(prefix="/products", tags=["Продукты"])

@router.get("/", response_model=Union[List[ProductShortResponse], dict])
async def get_all_products(db: AsyncSession = Depends(get_db)):
    query = select(Product) # Формирование запроса
    result = await db.execute(query) # Выполнение запроса
    products = result.scalars().all() # Ответ бд (список товаров)

    if not products: # Проверка есть ли вообще продукты
        return {"detail": "Товаров нет"} # Возврат сообщения если товаров нету
        
    return products # Ответ бд (список товаров)

@router.get("/{product_id}", response_model=ProductResponse)
async def get_one_product(product_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(Product)
        .where(Product.id == product_id) # Поиск по определенному Id
        .options(joinedload(Product.images)) # Запрос доп. фотографий
    )
    
    result = await db.execute(query) # Выполнение запроса
    product = result.scalars().unique().first() # Ответ бд
    
    if not product:  # Проверка на существование продукта
        raise HTTPException(
            status_code=404, # Возвращает ошибку
            detail="Товар не найден"# Сообщение ошибки
            )
    return product

@router.post("/create", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)# Путь: products/create | Response_model это класс ProductResponse в products/schemas.py | status_code это это код 201 который сообщает об успешном создании
async def create_product(product_data: ProductCreate, db: AsyncSession = Depends(get_db)):
    images_data = product_data.images # Список доп. фотографий, если их нет будет пустой список
    product_dict = product_data.model_dump(exclude={"images"}) # Превращение объекта схемы в словарь без  списка картинок (images_data)
    new_product = Product(
        title=product_data.title, # Название
        description=product_data.description, # Описание
        price=product_data.price, # Цена
        quantity=product_data.quantity, # Колличество
        preview_image=product_data.preview_image # Превью 
    )
    for img in images_data:  # Запуск цикла, если есть доп. фото
            db_image = ProductImage(image_path=img.image_path)
            new_product.images.append(db_image) # Привязка картинки к товару
        
    db.add(new_product) # Формирование запрорса
    await db.commit() # Создание записи в бд
    await db.refresh(new_product, attribute_names=["images"])
    
    return new_product
    