import shutil
import uuid
import time
from pathlib import Path
from fastapi import UploadFile, File, BackgroundTasks
from typing import List, Union
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db  
from app.products.models import Product, ProductImage, Category
from app.products.schemas import ProductResponse, ProductShortResponse, ProductCreate, CategoryCreate, CategoryResponse
from app.users.auth import get_current_user
from app.users.services import is_admin
from PIL import Image, ImageOps


# Это типо путь: /products автоматически ставится везде.Если к примеру @router.post("/register") то будет products/register
router = APIRouter(prefix="/products", tags=["Продукты"])

BASE_DIR = Path(__file__).resolve().parents[2] # Находит путь моего проекта
MAX_RAW_FILE_SIZE = 20 * 1024 * 1024 # Максимальный входяшего файла
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"} # Какие форматы файлов разрешены 
MAX_IMAGE_SIZE = (1024, 1024) # Разрешение фото

# Валидация фото
def validate_and_process_image(file: UploadFile) -> Image.Image:
    # Проверка формата
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл не является валидным изображением (разрешены JPG, PNG, WEBP)."
        )
    
    # Проврека веса файла
    if file.size > MAX_RAW_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл слишком большой для обработки."
        )
    
    try:
        # Открытие файла через pillow
        image = Image.open(file.file)
        
        # Проверка если с ориентацией картинки что-то не так
        if hasattr(image, '_getexif') and image._getexif() is not None: # Если данные о ориентации есть
            image = ImageOps.exif_transpose(image) # Нормальная ориентация 
            
        # Уменьшение картинки что б она вписалась в квадрат 1024x1024
        image.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)
        return image
    except Exception: # Если что-то пошло не так
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Не удалось прочитать изображение. Возможно, файл поврежден."
        )

# Удаляет файлы которые загрузили но не реализовали
def clean_expired_temp_files():
    temp_dir_path = BASE_DIR / "img" / "temp"
    if not temp_dir_path.exists():
        return
    current_time = time.time()
    max_age_seconds = 24 * 3600  # Перевод 24 часа в секунды 
    for file_path in temp_dir_path.iterdir(): # Цикл по всем файлам внутри img/temp
        if file_path.is_file():
            file_age = current_time - file_path.stat().st_mtime # Возвраст файла
            # Если лежит больше 24 часов то это мусор
            if file_age > max_age_seconds:
                try:
                    file_path.unlink()  # Удалине фалйа с диска
                    print(f"удален заброшенный файл {file_path.name}")
                except Exception as e:
                    print(f"Ошибка удаления файла {file_path.name}: {e}")

# Вывод каталога, минимальная информация
@router.get("/", response_model=Union[List[ProductShortResponse], dict])
async def get_all_products(db: AsyncSession = Depends(get_db)):
    query = select(Product)
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
        .options(joinedload(Product.images))  # Загрузка связанных картинок из БД
    )
    result = await db.execute(query)
    product = result.scalars().unique().first()
    if not product:
        raise HTTPException(
            status_code=404,
            detail="Товар не найден"
        )
    return product

# Сохранение товара превью и доп. фото в постоянную папку и запуск фоновой задачи для првоерки на мусор
@router.post(
    "/create", response_model=ProductResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[
        # Все функции которые выполнятся до запуска роута
        Depends(get_current_user),
        Depends(is_admin)
    ],
)
async def create_product(
    product_data: ProductCreate, 
    background_tasks: BackgroundTasks, # Инструмент фоновых задач
    db: AsyncSession = Depends(get_db)
):    
    
    # Перенос главного фото из временной папки в постоянную
    final_preview_db_path = None # Хранит путь картинки для записи в бд
    if product_data.preview_image: # Если путь к картинке есть
        temp_preview_path = BASE_DIR / product_data.preview_image # Путь к временному файлу
        if temp_preview_path.exists() and temp_preview_path.is_file(): # Если файл есть на жестком диске
            final_preview_dir = BASE_DIR / "img" / "previews" # Путь к постоянной папке
            final_preview_dir.mkdir(parents=True, exist_ok=True)
            final_preview_file = final_preview_dir / temp_preview_path.name # Итоговый путь файла внутри папки img/previews 
            # Перемещание файла с временной папки в постоянную. Str потому-что работает только с текстом
            shutil.move(str(temp_preview_path), str(final_preview_file))
            final_preview_db_path = f"img/previews/{temp_preview_path.name}" # Путь для записи в бд
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Файл главного превью {product_data.preview_image} не найден во временной папке."
            )

    # Модель нового товара
    new_product = Product(
        title=product_data.title,
        description=product_data.description,
        price=product_data.price,
        quantity=product_data.quantity,
        preview_image=final_preview_db_path,
        category_id=product_data.category_id,
    )

    # Перенос доп.фото из временной папки в постоянную
    for img in product_data.images: # Перебирает кажый объект картинки из списка доп фото
        temp_gallery_path = BASE_DIR / img.image_path # Полный адрес временной фотки
        # Если этот временный файл существует
        if temp_gallery_path.exists() and temp_gallery_path.is_file():
            # Создаем целевую постоянную папку для галереи товаров
            final_gallery_dir = BASE_DIR / "img" / "gallery" # Куда сохранять
            final_gallery_dir.mkdir(parents=True, exist_ok=True) # Создается папка если ее нет
            final_gallery_file = final_gallery_dir / temp_gallery_path.name # Финальный адрес (папка gallery + имя самой фотки)
            shutil.move(str(temp_gallery_path), str(final_gallery_file)) # Перенос из временной папки в постоянную
            final_gallery_db_path = f"img/gallery/{temp_gallery_path.name}" # Путь для записи в бд
            
            # Создаем объект модели картинки и крепим через связь .append() к нашему товару
            db_image = ProductImage(image_path=final_gallery_db_path)
            new_product.images.append(db_image)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Файл галереи {img.image_path} не найден во временной папке."
            )
        
    db.add(new_product) # Добавление товара в сессию бд
    await db.commit() # Сохранение в бд
    await db.refresh(new_product, attribute_names=["images"]) # Обновление информации
    background_tasks.add_task(clean_expired_temp_files) # Фоновая задача(удаляет мусор)
    
    return new_product

# Валидация, сжатие главного фото в WebP и сохранение во временную папку temp
@router.post("/upload-preview", tags=["Загрузка медиа"],
    dependencies=[
        # Все функции которые выполнятся до запуска роута
        Depends(get_current_user),
        Depends(is_admin)
    ],)
async def upload_preview_file(file: UploadFile = File(...)):
    img = validate_and_process_image(file) # Проверка файла
    target_dir = BASE_DIR / "img" / "temp" # Сначала все фото сохраня.тся в временную папку
    target_dir.mkdir(parents=True, exist_ok=True) # Создается временная папка если ее нет
    unique_name = f"preview_{uuid.uuid4()}.webp" # Уникальное имя
    file_path = target_dir / unique_name # Готовый адес файла
    img.save(file_path, format="WEBP", quality=80) # Сохранение изображения с качесвтом 80%
        
    # Возвращение верменного пути
    return {"image_path": f"img/temp/{unique_name}"}

# Валидация, сжатие доп. фото в WebP и сохранение во временную папку
@router.post("/upload-gallery", tags=["Загрузка медиа"],
    dependencies=[
        # Все функции которые выполнятся до запуска роута
        Depends(get_current_user),
        Depends(is_admin)
    ],)
async def upload_gallery_file(file: UploadFile = File(...)):
    img = validate_and_process_image(file) # Проверка файла
    target_dir = BASE_DIR / "img" / "temp" # Путь до временной папки
    target_dir.mkdir(parents=True, exist_ok=True) # Создание папки если ее нет
    unique_name = f"gallery_{uuid.uuid4()}.webp" # Уникальное имя
    file_path = target_dir / unique_name # Адрес файла
    img.save(file_path, format="WEBP", quality=80) # Сохранение изображения с качесвтом 80%
    return {"image_path": f"img/temp/{unique_name}"}# Возвращение верменного пути


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
