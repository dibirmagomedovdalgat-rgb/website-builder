import shutil
import uuid
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from typing import List, Union
from sqlalchemy import select, delete
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, AsyncSessionLocal
from app.products.models import Product, ProductImage, Category, TempUpload
from app.products.schemas import (ProductResponse, ProductShortResponse, ProductCreate, CategoryCreate, CategoryResponse, TempUploadResponse,)
from app.users.auth import get_current_user
from app.users.services import is_admin
from app.products.services import (BASE_DIR, TEMP_DIR, validate_and_process_image, get_verified_temp_file, clean_expired_temp_files,)

# Это типо путь: /products автоматически ставится везде. Если к примеру @router.post("/register") то будет products/register
router = APIRouter(prefix="/products", tags=["Продукты"])

# Вывод каталога, минимальная информация
@router.get("/", response_model=Union[List[ProductShortResponse], dict])
async def get_all_products(db: AsyncSession = Depends(get_db)):
    query = select(Product).options(joinedload(Product.category))
    result = await db.execute(query)
    products = result.scalars().all()
    if not products:
        return {"detail": "Товаров нет"}
    
    return products


# Детальные данные о товаре
@router.get("/{product_id}", response_model=ProductResponse)
async def get_one_product(product_id: int, db: AsyncSession = Depends(get_db)):
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(
            joinedload(Product.images), # Загрузка связанных картинок из бд
            joinedload(Product.category), # Загрузка категории из бд
        )
    )
    result = await db.execute(query)
    product = result.scalars().unique().first()
    if not product:
        raise HTTPException(
            status_code=404,
            detail="Товар не найден"
        )
    return product

# Валидация, сжатие фото в WebP и сохранение во временную папку temp
@router.post(
    "/upload-preview",
    response_model=TempUploadResponse,
    tags=["Загрузка медиа"],
    dependencies=[
        # Проверка что пользователь админ
        Depends(is_admin)
    ],
)
async def upload_preview_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    img = validate_and_process_image(file)  # Проверка файла
    TEMP_DIR.mkdir(parents=True, exist_ok=True)  # Создается временная папка если ее нет
    unique_name = f"preview_{uuid.uuid4()}.webp"  # Уникальное имя
    file_path = TEMP_DIR / unique_name  # Готовый путь к файлу
    img.save(file_path, format="WEBP", quality=80)  # Сохранение изображения с качеством 80%

    # Запись данных о файле что б не показывать путь к файлу
    temp_record = TempUpload(
        filename=unique_name,
        purpose="preview",
        user_id=current_user.id # Это уходит юзеру
    )
    db.add(temp_record)
    await db.commit()
    await db.refresh(temp_record)
        
    # Возвращение Id вместо пути
    return {"upload_id": temp_record.id}


# Валидация, сжатие доп. фото в WebP и сохранение во временную папку
@router.post(
    "/upload-gallery",
    response_model=TempUploadResponse,
    tags=["Загрузка медиа"],
    dependencies=[
        # Проверка что пользователь админ
        Depends(is_admin)
    ],
)
async def upload_gallery_file(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    img = validate_and_process_image(file)  # Проверка файла
    TEMP_DIR.mkdir(parents=True, exist_ok=True)  # Создание папки если ее нет
    unique_name = f"gallery_{uuid.uuid4()}.webp"  # Уникальное имя
    file_path = TEMP_DIR / unique_name  # Адрес файла
    img.save(file_path, format="WEBP", quality=80)  # Сохранение изображения с качеством 80%

    # Запись данных о файле что б не показывать путь к файлу
    temp_record = TempUpload(
        filename=unique_name,
        purpose="gallery",
        user_id=current_user.id # Это уходит юзеру
    )
    db.add(temp_record)
    await db.commit()
    await db.refresh(temp_record)

    return {"upload_id": temp_record.id}  # Возвращение Id вместо пути


# Сохранение товара, перенос превью и доп. фото в постоянную папку и запуск фоновой задачи для проверки на мусор
@router.post(
    "/create",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        # Проверка что пользователь админ
        Depends(is_admin)
    ],
)
async def create_product(
    product_data: ProductCreate, 
    background_tasks: BackgroundTasks,  # Инструмент фоновых задач
    current_user=Depends(get_current_user),  # Текущий админ для проверки владельца файлов
    db: AsyncSession = Depends(get_db)
):    
    final_preview_db_path = None  # Хранит путь картинки для записи в бд
    records_to_delete = []  # Список временных записей бд на удаление после переноса

    # Перенос главного фото из временной папки в постоянную по Id
    if product_data.preview_upload_id:
        query = select(TempUpload).where(
            TempUpload.id == product_data.preview_upload_id,
            TempUpload.user_id == current_user.id, # Кто загрузил
            TempUpload.purpose == "preview"
        )
        result = await db.execute(query)
        preview_record = result.scalar_one_or_none()

        if not preview_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Загрузка главного превью не найдена или недоступна."
            )

        temp_preview_path = get_verified_temp_file(preview_record.filename) # Путь к временному файлу
        final_preview_dir = BASE_DIR / "img" / "previews"  # Путь к постоянной папке
        final_preview_dir.mkdir(parents=True, exist_ok=True)
        final_preview_file = final_preview_dir / temp_preview_path.name  # Итоговый путь файла внутри папки img/previews 
        # Перемещение файла с временной папки в постоянную. Str потому-что работает только с текстом
        shutil.move(str(temp_preview_path), str(final_preview_file))
        final_preview_db_path = f"img/previews/{temp_preview_path.name}"  # Путь для записи в бд
        records_to_delete.append(preview_record)  # Добавление в список на удаление

    # Модель нового товара
    new_product = Product(
        title=product_data.title,
        description=product_data.description,
        price=product_data.price,
        quantity=product_data.quantity,
        preview_image=final_preview_db_path,
        category_id=product_data.category_id,
    )

    # Перенос доп. фото из временной папки в постоянную по их Id
    if product_data.images:
        upload_ids = [img.upload_id for img in product_data.images] # Список из Id

        # Защита от передачи одинаковых ID в одном запросе
        if len(upload_ids) != len(set(upload_ids)): # Если были дублирующиеся Id
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Переданы дублирующиеся Id изображений."
            )

        # Загрузка с бд все черновики для галереи и упаковка в словарь
        query = select(TempUpload).where(
            TempUpload.id.in_(upload_ids),
            TempUpload.user_id == current_user.id,
            TempUpload.purpose == "gallery"
        )
        result = await db.execute(query)
        gallery_records = {rec.id: rec for rec in result.scalars().all()}

        # Проверяем, что все переданные ID реально существуют и принадлежат админу
        if len(gallery_records) != len(upload_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Одно или несколько изображений галереи не найдены или недоступны."
            )

        final_gallery_dir = BASE_DIR / "img" / "gallery" # Куда сохранять
        final_gallery_dir.mkdir(parents=True, exist_ok=True) # Создается папка если ее нет

        for uid in upload_ids:  # Цикл по Id
            rec = gallery_records[uid]
            temp_gallery_path = get_verified_temp_file(rec.filename) # Проверка файла и получение его пути во временной папке
            final_gallery_file = final_gallery_dir / temp_gallery_path.name # Готовый путь файла для постоянной папки
            shutil.move(str(temp_gallery_path), str(final_gallery_file)) # Перенос из временной папки в постоянную
            final_gallery_db_path = f"img/gallery/{temp_gallery_path.name}" # Путь для записи в бд
            
            # Создаем объект модели картинки и крепим через связь .append() к нашему товару
            db_image = ProductImage(image_path=final_gallery_db_path) # Запись картинки для бд
            new_product.images.append(db_image) # Привязывание картинки к товару
            records_to_delete.append(rec) # Добавление в список на удаление

    # Удаление временных записей с бд
    for rec in records_to_delete:
        await db.delete(rec)
        
    db.add(new_product) # Добавление товара в сессию бд
    await db.commit() # Сохранение в бд
    await db.refresh(new_product, attribute_names=["images", "category"]) # Обновление информации
    background_tasks.add_task(clean_expired_temp_files) # Удаление мусора
    
    return new_product

# Создание категории
@router.post("/categories/create", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED, tags=["Категории"],
    dependencies=[
        # Все функции которые выполнятся до запуска роута
        Depends(get_current_user),
        Depends(is_admin)
    ],)
async def create_category(category_data: CategoryCreate, db: AsyncSession = Depends(get_db)):    
    # Формирование запроса на поиск категории для проверки
    query = select(Category).where(Category.title == category_data.title)
    result = await db.execute(query) # Запрос бд
    existing_category = result.scalars().first() # Ответ бд
    
    # Если такая категория уже есть
    if existing_category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Категория с названием '{category_data.title}' уже существует."
        )
        
    # Если такой категории нет
    new_category = Category(
        title=category_data.title  # Название категории
    )
    
    db.add(new_category) # Добавление в сессию бд
    await db.commit() # Сохранение в бд
    await db.refresh(new_category) # Обновление информации (получаем ID)
    
    return new_category # Возвращение созданной категории

# Удаление категории
@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Категории"],
    dependencies=[
        Depends(get_current_user),
        Depends(is_admin)
    ],
)
async def delete_category(category_id: int, db: AsyncSession = Depends(get_db)):
    query = select(Category).where(Category.id == category_id)
    result = await db.execute(query)
    category = result.scalars().first()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Категория не найдена"
        )

    await db.delete(category)
    await db.commit()

# Удаление товара
@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_user), Depends(is_admin)],
)
async def delete_product(product_id: int, db: AsyncSession = Depends(get_db)):
    query = select(Product).where(Product.id == product_id)
    result = await db.execute(query)
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден"
        )

    await db.delete(product)
    await db.commit()


# Обновление данных товара
@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    dependencies=[Depends(get_current_user), Depends(is_admin)],
)
async def update_product(
    product_id: int,
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Product)
        .where(Product.id == product_id)
        .options(joinedload(Product.images), joinedload(Product.category))
    )
    result = await db.execute(query)
    product = result.scalars().unique().first()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не найден")

    product.title = product_data.title
    product.description = product_data.description
    product.price = product_data.price
    product.quantity = product_data.quantity
    product.category_id = product_data.category_id

    await db.commit()
    await db.refresh(product, attribute_names=["images", "category"])
    return product